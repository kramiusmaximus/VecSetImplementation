import base64
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from typing import Dict, Optional

import requests
import runpod

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VECSET_SCRIPT = os.path.join(REPO_DIR, "vecset_edit.py")
TEXTURE_SCRIPT = os.path.join(REPO_DIR, "preserving_texture_baking.py")


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _download(url: str, dest_path: str, timeout: int = 60) -> None:
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _write_base64(data_b64: str, dest_path: str) -> None:
    raw = base64.b64decode(data_b64)
    with open(dest_path, "wb") as f:
        f.write(raw)


def _get_input_file(
    input_data: Dict,
    key_prefix: str,
    dest_dir: str,
    default_name: str,
) -> Optional[str]:
    url_key = f"{key_prefix}_url"
    b64_key = f"{key_prefix}_base64"
    name_key = f"{key_prefix}_filename"

    filename = input_data.get(name_key) or default_name
    dest_path = os.path.join(dest_dir, filename)

    if url_key in input_data and input_data[url_key]:
        _download(input_data[url_key], dest_path)
        return dest_path

    if b64_key in input_data and input_data[b64_key]:
        _write_base64(input_data[b64_key], dest_path)
        return dest_path

    return None


def _run_cmd(cmd, workdir):
    result = subprocess.run(
        cmd,
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    log = []
    log.append("$ " + " ".join(cmd))
    if result.stdout:
        log.append(result.stdout)
    if result.stderr:
        log.append(result.stderr)
    return result.returncode, "\n".join(log)


def _zip_dir(src_dir: str, dest_base: str) -> str:
    archive_path = shutil.make_archive(dest_base, "zip", src_dir)
    return archive_path


def _encode_file(path: str) -> Dict:
    with open(path, "rb") as f:
        data = f.read()
    return {
        "filename": os.path.basename(path),
        "size_bytes": len(data),
        "base64": base64.b64encode(data).decode("utf-8"),
    }


def _collect_outputs(output_dir: str) -> Dict[str, str]:
    outputs = {}
    candidates = [
        "edited_mesh.glb",
        "edited_mesh_views.png",
        "selected_fixed_tokens_views.png",
        "2d_masked_input.png",
        "mv_repaint_model.glb",
        "mv_adapter_repaint_6_views.png",
        "mv_adapter_6_views.png",
    ]
    for name in candidates:
        path = os.path.join(output_dir, name)
        if os.path.exists(path):
            outputs[name] = path
    return outputs


def handler(job):
    input_data = job.get("input", {})

    if input_data.get("dry_run") is True:
        return {
            "status": "ok",
            "message": "dry_run: handler is reachable",
        }

    run_id = input_data.get("run_id") or f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    work_dir = tempfile.mkdtemp(prefix=f"vecset_{run_id}_")
    input_dir = os.path.join(work_dir, "input")
    output_dir = os.path.join(work_dir, "output")
    _safe_mkdir(input_dir)
    _safe_mkdir(output_dir)

    mesh_path = _get_input_file(input_data, "mesh", input_dir, "model.glb")
    edit_path = _get_input_file(input_data, "edit_image", input_dir, "2d_edit.png")
    mask_path = _get_input_file(input_data, "mask_image", input_dir, "2d_mask.png")
    render_path = _get_input_file(input_data, "render_image", input_dir, "2d_render.png")

    missing = [
        name
        for name, path in [
            ("mesh", mesh_path),
            ("edit_image", edit_path),
            ("mask_image", mask_path),
        ]
        if path is None
    ]
    if missing:
        return {
            "status": "error",
            "message": f"Missing required inputs: {', '.join(missing)}",
        }

    azimuth = float(input_data.get("azimuth", 0.0))
    elevation = float(input_data.get("elevation", 0.0))
    scale = float(input_data.get("scale", 2.0))
    attentive_2d = int(input_data.get("attentive_2d", 8))
    cut_off_p = float(input_data.get("cut_off_p", 0.5))
    topk_percent_2d = float(input_data.get("topk_percent_2d", 0.2))
    threshold_percent_2d = float(input_data.get("threshold_percent_2d", 0.1))
    step_pruning = int(input_data.get("step_pruning", 5))
    edit_strength = float(input_data.get("edit_strength", 0.7))
    guidance_scale = float(input_data.get("guidance_scale", 7.5))

    cmd = [
        "python",
        VECSET_SCRIPT,
        "--input_dir",
        input_dir,
        "--output_dir",
        output_dir,
        "--mesh_file",
        os.path.basename(mesh_path),
        "--edit_image",
        os.path.basename(edit_path),
        "--mask_image",
        os.path.basename(mask_path),
        "--azimuth",
        str(azimuth),
        "--elevation",
        str(elevation),
        "--scale",
        str(scale),
        "--attentive_2d",
        str(attentive_2d),
        "--cut_off_p",
        str(cut_off_p),
        "--topk_percent_2d",
        str(topk_percent_2d),
        "--threshold_percent_2d",
        str(threshold_percent_2d),
        "--step_pruning",
        str(step_pruning),
        "--edit_strength",
        str(edit_strength),
        "--guidance_scale",
        str(guidance_scale),
    ]

    if render_path is not None:
        cmd.extend(["--render_image", os.path.basename(render_path)])

    code, log = _run_cmd(cmd, REPO_DIR)
    if code != 0:
        return {
            "status": "error",
            "message": "vecset_edit failed",
            "log": log,
        }

    texture_log = None
    if input_data.get("run_texture_repaint") is True:
        seed = int(input_data.get("seed", 99999))
        render_method = input_data.get("render_method", "nvdiffrast")
        cmd2 = [
            "python",
            TEXTURE_SCRIPT,
            "--input_mesh",
            os.path.join(output_dir, "edited_mesh.glb"),
            "--ref_mesh",
            os.path.join(output_dir, "source_model.glb"),
            "--texture_image",
            os.path.join(output_dir, "2d_edit.png"),
            "--output_dir",
            output_dir,
            "--seed",
            str(seed),
            "--render_method",
            str(render_method),
        ]
        code2, log2 = _run_cmd(cmd2, REPO_DIR)
        texture_log = log2
        if code2 != 0:
            return {
                "status": "error",
                "message": "texture repaint failed",
                "log": log + "\n\n" + log2,
            }

    outputs = _collect_outputs(output_dir)

    result = {
        "status": "ok",
        "run_id": run_id,
        "outputs": list(outputs.keys()),
        "log": log if not texture_log else log + "\n\n" + texture_log,
    }

    if input_data.get("return_files") is True:
        result["files"] = {name: _encode_file(path) for name, path in outputs.items()}

    if input_data.get("return_zip_base64") is True:
        archive_path = _zip_dir(output_dir, os.path.join(work_dir, "results"))
        result["zip"] = _encode_file(archive_path)

    return result


runpod.serverless.start({"handler": handler})

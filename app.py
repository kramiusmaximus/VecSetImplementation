import os
import sys
import shutil
import subprocess
import logging
import tempfile
from datetime import datetime
import uuid

import gradio as gr

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(ROOT_DIR, "runs")
LOG_DIR = os.path.join(ROOT_DIR, "logs")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _setup_logging() -> logging.Logger:
    _ensure_dir(LOG_DIR)
    logger = logging.getLogger("vecset_edit_app")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, "requests.log"))
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


LOGGER = _setup_logging()


def _run_cmd(cmd, workdir, env=None):
    result = subprocess.run(
        cmd,
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
    )
    log = []
    log.append("$ " + " ".join(cmd))
    if result.stdout:
        log.append(result.stdout)
        for line in result.stdout.splitlines():
            LOGGER.info("subprocess_stdout %s", line)
    if result.stderr:
        log.append(result.stderr)
        for line in result.stderr.splitlines():
            LOGGER.error("subprocess_stderr %s", line)
    return result.returncode, "\n".join(log)


def _copy_uploaded(src_path: str, dest_dir: str, dest_name: str) -> str:
    _ensure_dir(dest_dir)
    dest_path = os.path.join(dest_dir, dest_name)
    shutil.copy2(src_path, dest_path)
    return dest_path


def _new_run_dir():
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{stamp}_{uuid.uuid4().hex[:8]}"
    run_dir = os.path.join(RUNS_DIR, run_id)
    input_dir = os.path.join(run_dir, "input")
    output_dir = os.path.join(run_dir, "output")
    _ensure_dir(input_dir)
    _ensure_dir(output_dir)
    return run_dir, input_dir, output_dir


def _zip_dir(src_dir: str, dest_base: str) -> str:
    archive_path = shutil.make_archive(dest_base, "zip", src_dir)
    return archive_path


def run_vecset_edit(
    mesh_file,
    edit_image,
    mask_image,
    render_image,
    azimuth,
    elevation,
    scale,
    attentive_2d,
    cut_off_p,
    topk_percent_2d,
    threshold_percent_2d,
    step_pruning,
    edit_strength,
    guidance_scale,
    run_texture_repaint,
    seed,
    render_method,
    progress=gr.Progress(track_tqdm=True),
    request: gr.Request | None = None,
):
    try:
        if mesh_file is None or edit_image is None or mask_image is None:
            return (
                None,
                None,
                None,
                None,
                None,
                "Missing required inputs: mesh, edited image, and mask image are required.",
            )

        progress(0.02, desc="Preparing run directory")
        run_dir, input_dir, output_dir = _new_run_dir()

        client_host = None
        if request is not None:
            client_host = getattr(getattr(request, "client", None), "host", None)
        LOGGER.info(
            "request_start run_id=%s client=%s mesh=%s edit=%s mask=%s render=%s az=%s el=%s scale=%s attentive_2d=%s cut_off_p=%s topk=%s threshold=%s step_pruning=%s edit_strength=%s guidance_scale=%s texture_repaint=%s seed=%s render_method=%s",
            os.path.basename(run_dir),
            client_host,
            os.path.basename(mesh_file) if mesh_file else None,
            os.path.basename(edit_image) if edit_image else None,
            os.path.basename(mask_image) if mask_image else None,
            os.path.basename(render_image) if render_image else None,
            azimuth,
            elevation,
            scale,
            attentive_2d,
            cut_off_p,
            topk_percent_2d,
            threshold_percent_2d,
            step_pruning,
            edit_strength,
            guidance_scale,
            run_texture_repaint,
            seed,
            render_method,
        )

        mesh_name = os.path.basename(mesh_file)
        edit_name = os.path.basename(edit_image)
        mask_name = os.path.basename(mask_image)

        _copy_uploaded(mesh_file, input_dir, mesh_name)
        _copy_uploaded(edit_image, input_dir, edit_name)
        _copy_uploaded(mask_image, input_dir, mask_name)

        render_name = None
        if render_image:
            render_name = os.path.basename(render_image)
            _copy_uploaded(render_image, input_dir, render_name)

        progress(0.08, desc="Launching VecSetEdit")
        cmd = [
        sys.executable,
        "vecset_edit.py",
        "--input_dir",
        input_dir,
        "--output_dir",
        output_dir,
        "--mesh_file",
        mesh_name,
        "--edit_image",
        edit_name,
        "--mask_image",
        mask_name,
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
        if render_name:
            cmd.extend(["--render_image", render_name])

        progress(0.15, desc="Running VecSetEdit (this can take a while)")
        code, log = _run_cmd(cmd, ROOT_DIR)
        if code != 0:
            LOGGER.error("request_failed run_id=%s exit_code=%s", os.path.basename(run_dir), code)
            return (
                None,
                None,
                None,
                None,
                None,
                f"VecSetEdit failed (exit code {code}).\n\n{log}",
            )

        progress(0.75, desc="Collecting outputs")
        edited_mesh = os.path.join(output_dir, "edited_mesh.glb")
        edited_views = os.path.join(output_dir, "edited_mesh_views.png")
        selected_views = os.path.join(output_dir, "selected_fixed_tokens_views.png")
        masked_input = os.path.join(output_dir, "2d_masked_input.png")

        texture_mesh = None
        if run_texture_repaint:
            progress(0.8, desc="Running texture repaint")
            cmd2 = [
            sys.executable,
            "preserving_texture_baking.py",
            "--input_mesh",
            edited_mesh,
            "--ref_mesh",
            os.path.join(output_dir, "source_model.glb"),
            "--texture_image",
            os.path.join(output_dir, "2d_edit.png"),
            "--output_dir",
            output_dir,
            "--seed",
            str(seed),
            "--render_method",
            render_method,
            ]
            code2, log2 = _run_cmd(cmd2, ROOT_DIR)
            log = log + "\n\n" + log2
            if code2 == 0:
                texture_mesh = os.path.join(output_dir, "mv_repaint_model.glb")
            else:
                log = log + f"\nTexture repaint failed (exit code {code2})."
                LOGGER.error("texture_repaint_failed run_id=%s exit_code=%s", os.path.basename(run_dir), code2)

        progress(0.92, desc="Packaging results")
        archive_path = _zip_dir(output_dir, os.path.join(run_dir, "results"))

        progress(1.0, desc="Done")
        LOGGER.info("request_done run_id=%s", os.path.basename(run_dir))
        return (
            edited_mesh if os.path.exists(edited_mesh) else None,
            texture_mesh if texture_mesh and os.path.exists(texture_mesh) else None,
            masked_input if os.path.exists(masked_input) else None,
            selected_views if os.path.exists(selected_views) else None,
            edited_views if os.path.exists(edited_views) else None,
            archive_path if os.path.exists(archive_path) else None,
            log,
        )
    except Exception:
        LOGGER.exception("request_exception")
        raise


with gr.Blocks(title="VecSetEdit GUI") as demo:
    gr.Markdown(
        """
# VecSetEdit Web GUI

Upload a mesh and 2D edit/mask images to run VecSetEdit. Optionally run texture repaint.

Notes:
- `render image` is optional. If omitted, the edited image is used as reference.
- This requires a CUDA GPU and the repo dependencies listed in `README.md`.
"""
    )

    with gr.Row():
        mesh_file = gr.File(
            label="Mesh file (.glb/.obj/.ply)",
            file_types=[".glb", ".gltf", ".obj", ".ply"],
            type="filepath",
        )
        edit_image = gr.File(
            label="Edited image (2d_edit.png)",
            file_types=[".png", ".jpg", ".jpeg"],
            type="filepath",
        )
        mask_image = gr.File(
            label="Mask image (2d_mask.png)",
            file_types=[".png", ".jpg", ".jpeg"],
            type="filepath",
        )
        render_image = gr.File(
            label="Render image (optional)",
            file_types=[".png", ".jpg", ".jpeg"],
            type="filepath",
        )

    with gr.Row():
        azimuth = gr.Number(label="Azimuth (radians)", value=0.0)
        elevation = gr.Number(label="Elevation (radians)", value=0.0)
        scale = gr.Number(label="Scale", value=2.0)
        attentive_2d = gr.Number(label="Attentive 2D tokens", value=8, precision=0)
        cut_off_p = gr.Number(label="Cut-off percentage", value=0.5)
        topk_percent_2d = gr.Number(label="Top-k percent 2D", value=0.2)
        threshold_percent_2d = gr.Number(label="Threshold percent 2D", value=0.1)
        step_pruning = gr.Number(label="Step pruning", value=5, precision=0)
        edit_strength = gr.Number(label="Edit strength", value=0.7)
        guidance_scale = gr.Number(label="Guidance scale", value=7.5)

    with gr.Row():
        run_texture_repaint = gr.Checkbox(label="Run texture repaint (preserving_texture_baking)", value=False)
        seed = gr.Number(label="Texture seed", value=99999, precision=0)
        render_method = gr.Dropdown(
            label="Texture render method",
            choices=["nvdiffrast", "bpy"],
            value="nvdiffrast",
        )

    with gr.Row():
        run_btn = gr.Button("Run VecSetEdit", variant="primary")
        clear_btn = gr.ClearButton(
            [mesh_file, edit_image, mask_image, render_image],
            value="Clear inputs",
        )

    with gr.Row():
        edited_mesh_out = gr.Model3D(label="Edited mesh")
        texture_mesh_out = gr.Model3D(label="Textured mesh (mv_repaint_model.glb)")

    with gr.Row():
        masked_input_out = gr.Image(label="Masked input overlay", type="filepath")
        selected_views_out = gr.Image(label="Selected token views", type="filepath")
        edited_views_out = gr.Image(label="Edited mesh views", type="filepath")

    download_out = gr.File(label="Download results (.zip)")
    log_out = gr.Textbox(label="Logs", lines=18)

    run_btn.click(
        fn=run_vecset_edit,
        inputs=[
            mesh_file,
            edit_image,
            mask_image,
            render_image,
            azimuth,
            elevation,
            scale,
            attentive_2d,
            cut_off_p,
            topk_percent_2d,
            threshold_percent_2d,
            step_pruning,
            edit_strength,
            guidance_scale,
            run_texture_repaint,
            seed,
            render_method,
        ],
        outputs=[
            edited_mesh_out,
            texture_mesh_out,
            masked_input_out,
            selected_views_out,
            edited_views_out,
            download_out,
            log_out,
        ],
    )


def main():
    _ensure_dir(RUNS_DIR)
    demo.queue(max_size=4).launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()

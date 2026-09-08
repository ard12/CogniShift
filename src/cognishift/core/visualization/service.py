"""
Deterministic Visualization Service for CogniShift.
Orchestrates contract parsing, data extraction, Matplotlib rendering,
cryptographic validation, and SQLite artifact registration.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from cognishift.app.db.database import get_db
from cognishift.core.artifact_generators import create_and_register_artifact
from cognishift.core.security import get_workspace_root
from cognishift.core.visualization.renderer import render_visualization
from cognishift.core.visualization.schemas import (
    ArtifactRequestContract,
    ChartType,
    VisualizationResult,
    VisualizationSpec,
)
from cognishift.core.visualization.selector import (
    build_visualization_specs,
    parse_artifact_request_contract,
)
from cognishift.core.visualization.validator import validate_png_artifact

logger = logging.getLogger(__name__)


async def execute_visualization_pipeline(
    file_path: Path,
    query: str,
    workspace_id: int,
    run_id: int,
    contract: Optional[ArtifactRequestContract] = None
) -> List[VisualizationResult]:
    """
    Executes the deterministic visualization pipeline for a resolved source file.
    Guarantees that every generated PNG is grounded in real source data, structurally validated,
    and registered as a first-class workspace artifact.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return [
            VisualizationResult(
                success=False,
                error=f"Source file not found: {file_path.name}"
            )
        ]

    contract = contract or parse_artifact_request_contract(query)
    results: List[VisualizationResult] = []

    try:
        specs = build_visualization_specs(file_path, contract, query)
    except Exception as spec_err:
        logger.error(f"Failed to build visualization specs: {spec_err}")
        return [
            VisualizationResult(
                success=False,
                error=f"Data extraction failed: {str(spec_err)}"
            )
        ]

    ws_root = get_workspace_root(workspace_id)
    run_dir = ws_root / f"generated/run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    for idx, spec in enumerate(specs):
        dest_filename = spec.output_filename
        dest_path = run_dir / dest_filename

        try:
            # 1. Render visualization directly with trusted matplotlib service
            render_visualization(spec, dest_path)

            # 2. Strict validation of generated PNG file
            is_valid, val_msg = validate_png_artifact(dest_path)
            if not is_valid:
                logger.error(f"PNG validation failed for {dest_filename}: {val_msg}")
                results.append(
                    VisualizationResult(
                        success=False,
                        filename=dest_filename,
                        error=f"Validation failure: {val_msg}",
                        spec=spec
                    )
                )
                continue

            file_size = dest_path.stat().st_size

            # 3. Register as authoritative workspace artifact in SQLite
            def _generator_wrapper(p: Path):
                # Copy the validated file to target path
                import shutil
                shutil.copy2(str(dest_path), str(p))

            registered = await create_and_register_artifact(
                workspace_id=workspace_id,
                filename=dest_filename,
                artifact_type="png",
                generator_fn=_generator_wrapper,
                title=spec.title,
                description=f"Generated from {spec.source_file} (Sheet: {spec.source_sheet or 'Default'}). {spec.provenance.get('transformation', '')}",
                run_id=run_id,
                metadata=spec.provenance
            )

            results.append(
                VisualizationResult(
                    success=True,
                    artifact_id=registered.get("id"),
                    filename=dest_filename,
                    file_path=str(dest_path),
                    file_size=file_size,
                    spec=spec
                )
            )

        except Exception as ren_err:
            logger.error(f"Error rendering visualization spec #{idx+1}: {ren_err}")
            results.append(
                VisualizationResult(
                    success=False,
                    filename=dest_filename,
                    error=f"Rendering failed: {str(ren_err)}",
                    spec=spec
                )
            )

    return results

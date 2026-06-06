"""FastAPI application for Trash Sorter Pro local agent."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect

from app.agent.auth import (
    AuthContext,
    authenticate_token_values,
    require_admin_token,
    require_user_token,
)
from app.agent.runtime import STREAM_FRAME_INTERVAL_S, AgentRuntime
from app.agent.schemas import (
    ActionResult,
    ActuationTestModeRequest,
    ActuationTestModeResponse,
    AnnotationRequest,
    AuthMeResponse,
    BulkDatasetRequest,
    CameraSampleRequest,
    CaptureSessionFrameRequest,
    CaptureSessionResponse,
    CaptureSessionStartRequest,
    CommonWasteCatalogResponse,
    DatasetAnnotationResponse,
    DatasetBoxDTO,
    DatasetItemDTO,
    DatasetItemsResponse,
    DatasetSummaryDTO,
    DeleteRequest,
    HardwareAudioTestRequest,
    HardwareAudioTestResponse,
    HardwareDiagnosticsResponse,
    HardwareMp3TestRequest,
    HardwareMp3TestResponse,
    HardwareProfileResponse,
    HardwareTestRequest,
    HardwareTestResponse,
    HealthResponse,
    HistoryResponse,
    HistoryRowDTO,
    ManualUrlImportRequest,
    MappingsResponse,
    ModelClassesResponse,
    RelabelRequest,
    RuntimeStatus,
    ServoAngleTestRequest,
    ServoAngleTestResponse,
    SettingsResponse,
    SortAngleTestRequest,
    TrainingStatusDTO,
    UserDashboardResponse,
)
from app.agent.user_dashboard import build_user_dashboard
from app.core.common_waste_catalog import common_waste_catalog
from app.core.config import AppConfig, ClassMapping
from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_queue import (
    delete_queue_items,
    import_manual_image_urls,
    import_manual_images,
    is_trusted_meta,
    mark_items_trusted,
    quarantine_queue_items,
    quarantine_untrusted_items,
    relabel_images,
    save_item_annotations,
    summarize_queue,
)
from app.core.history import HistoryService
from app.core.waste_categories import (
    canonical_class_name,
    category_for_class,
    default_class_id_for_name,
)
from app.utils.dataset_import import import_yolo_dataset_to_queue
from app.utils.paths import config_path, dataset_db_path, db_path, logs_dir


def create_app(
    *,
    runtime: AgentRuntime | None = None,
    config_file: Path | None = None,
    history_file: Path | None = None,
    dataset_file: Path | None = None,
) -> FastAPI:
    rt = runtime or AgentRuntime(
        config_file=config_file or config_path(),
        history_file=history_file or db_path(),
        dataset_file=dataset_file or dataset_db_path(),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            rt.close()

    app = FastAPI(title="Trash Sorter Pro Agent", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.runtime = rt

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    user_router = APIRouter(prefix="/api", dependencies=[Depends(require_user_token)])

    @user_router.get("/me", response_model=AuthMeResponse)
    def me(context: Annotated[AuthContext, Depends(require_user_token)]) -> AuthMeResponse:
        return AuthMeResponse(
            role=context.role,
            capabilities=context.capabilities,
            auth_required=context.auth_required,
        )

    @user_router.get("/user/dashboard", response_model=UserDashboardResponse)
    def user_dashboard() -> UserDashboardResponse:
        return build_user_dashboard(rt)

    router = APIRouter(prefix="/api", dependencies=[Depends(require_admin_token)])

    @router.get("/status", response_model=RuntimeStatus)
    def status(include_devices: bool = True) -> RuntimeStatus:
        return rt.status(include_devices=include_devices)

    @router.get("/hardware/profile", response_model=HardwareProfileResponse)
    def hardware_profile() -> HardwareProfileResponse:
        return HardwareProfileResponse(**rt.hardware_profile())

    @router.post("/hardware/test", response_model=HardwareTestResponse)
    def hardware_test(payload: HardwareTestRequest) -> HardwareTestResponse:
        return HardwareTestResponse(**rt.test_hardware(payload.command))

    @router.post("/hardware/audio-test", response_model=HardwareAudioTestResponse)
    def hardware_audio_test(payload: HardwareAudioTestRequest) -> HardwareAudioTestResponse:
        return HardwareAudioTestResponse(**rt.test_audio(payload.track))

    @router.post("/hardware/mp3-test", response_model=HardwareMp3TestResponse)
    def hardware_mp3_test(payload: HardwareMp3TestRequest) -> HardwareMp3TestResponse:
        return HardwareMp3TestResponse(**rt.test_mp3(payload.command, payload.value))

    @router.post("/hardware/servo-angle", response_model=ServoAngleTestResponse)
    def hardware_servo_angle(payload: ServoAngleTestRequest) -> ServoAngleTestResponse:
        return ServoAngleTestResponse(**rt.test_servo_angles(payload.d6, payload.d7, payload.label))

    @router.post("/hardware/home-angle", response_model=ServoAngleTestResponse)
    def hardware_home_angle(payload: ServoAngleTestRequest) -> ServoAngleTestResponse:
        return ServoAngleTestResponse(**rt.test_home_angles(payload.d6, payload.d7, payload.label))

    @router.post("/hardware/sort-angle", response_model=ServoAngleTestResponse)
    def hardware_sort_angle(payload: SortAngleTestRequest) -> ServoAngleTestResponse:
        return ServoAngleTestResponse(
            **rt.test_sort_angles(payload.command, payload.d6, payload.d7, payload.label)
        )

    @router.get("/hardware/diagnostics", response_model=HardwareDiagnosticsResponse)
    def hardware_diagnostics() -> HardwareDiagnosticsResponse:
        return HardwareDiagnosticsResponse(**rt.hardware_diagnostics())

    @router.post("/hardware/reconnect", response_model=HardwareDiagnosticsResponse)
    def hardware_reconnect() -> HardwareDiagnosticsResponse:
        return HardwareDiagnosticsResponse(**rt.reconnect_hardware())

    @router.get("/actuation/test-mode", response_model=ActuationTestModeResponse)
    def actuation_test_mode() -> ActuationTestModeResponse:
        return ActuationTestModeResponse(**rt.actuation_test_mode())

    @router.put("/actuation/test-mode", response_model=ActuationTestModeResponse)
    def put_actuation_test_mode(payload: ActuationTestModeRequest) -> ActuationTestModeResponse:
        return ActuationTestModeResponse(**rt.set_actuation_test_mode(payload.enabled))

    @router.post("/devices/refresh", response_model=RuntimeStatus)
    def refresh_devices() -> RuntimeStatus:
        return rt.refresh_devices()

    @router.post("/camera/start", response_model=ActionResult)
    def camera_start() -> ActionResult:
        ok, msg = rt.start_camera()
        return ActionResult(ok=ok, message=msg)

    @router.post("/camera/stop", response_model=ActionResult)
    def camera_stop() -> ActionResult:
        ok, msg = rt.stop_camera()
        return ActionResult(ok=ok, message=msg)

    @app.get("/api/camera/stream")
    async def camera_stream(token: str | None = None) -> StreamingResponse:
        _require_stream_token(token)

        async def frames():
            while True:
                frame = rt.latest_jpeg()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
                await asyncio.sleep(STREAM_FRAME_INTERVAL_S)

        return StreamingResponse(
            frames(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.get("/settings", response_model=SettingsResponse)
    def get_settings() -> SettingsResponse:
        return SettingsResponse(config=rt.cfg)

    @router.put("/settings", response_model=SettingsResponse)
    def put_settings(cfg: AppConfig) -> SettingsResponse:
        return SettingsResponse(config=rt.update_config(cfg))

    @router.get("/mappings", response_model=MappingsResponse)
    def get_mappings() -> MappingsResponse:
        return MappingsResponse(mappings=rt.cfg.mappings)

    @router.get("/model/classes", response_model=ModelClassesResponse)
    def get_model_classes() -> ModelClassesResponse:
        classes = [
            {"id": cls_id, "name": name}
            for cls_id, name in sorted(rt.model_classes().items())
        ]
        return ModelClassesResponse(classes=classes)

    @router.get("/common-waste/catalog", response_model=CommonWasteCatalogResponse)
    def get_common_waste_catalog() -> CommonWasteCatalogResponse:
        return CommonWasteCatalogResponse(items=common_waste_catalog())

    @router.get("/training/status", response_model=TrainingStatusDTO)
    def training_status() -> TrainingStatusDTO:
        return _training_status(_project_root())

    @router.put("/mappings", response_model=MappingsResponse)
    def put_mappings(mappings: list[ClassMapping]) -> MappingsResponse:
        cfg = rt.update_mappings(_clean_mappings(mappings))
        return MappingsResponse(mappings=cfg.mappings)

    @router.get("/history", response_model=HistoryResponse)
    def get_history(
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
        offset: Annotated[int, Query(ge=0)] = 0,
        cls_name: str | None = None,
    ) -> HistoryResponse:
        service = HistoryService(rt.history_file)
        try:
            rows = service.query(limit=limit, offset=offset, cls_name=cls_name)
        finally:
            service.close()
        dto_rows = [_history_row_to_dto(row) for row in rows]
        return HistoryResponse(rows=dto_rows, total=len(dto_rows))

    @router.get("/history/export.csv")
    def export_history() -> Response:
        service = HistoryService(rt.history_file)
        try:
            rows = service.query(limit=1_000_000)
        finally:
            service.close()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        cols = [
            "id",
            "track_id",
            "ts",
            "cls_id",
            "cls_name",
            "conf",
            "bbox_x1",
            "bbox_y1",
            "bbox_x2",
            "bbox_y2",
            "image_path",
            "annotated_path",
            "meta_path",
            "route_label",
            "bin_index",
            "uart_command",
            "ack_status",
            "rtt_ms",
        ]
        writer.writerow(cols)
        for row in rows:
            writer.writerow([getattr(row, col, "") for col in cols])
        return Response(
            buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=trash-sorter-history.csv"},
        )

    @router.get("/history/{row_id}/image")
    def history_image(
        row_id: int,
        kind: Annotated[Literal["annotated", "raw"], Query()] = "annotated",
    ) -> FileResponse:
        service = HistoryService(rt.history_file)
        try:
            row = service.get(row_id)
        finally:
            service.close()
        if row is None:
            raise HTTPException(status_code=404, detail="History row not found")
        path_value = (
            getattr(row, "annotated_path", None)
            if kind == "annotated"
            else getattr(row, "image_path", None)
        )
        image_path = Path(str(path_value or ""))
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Detection image not found")
        return FileResponse(image_path)

    @router.get("/dataset/summary", response_model=DatasetSummaryDTO)
    def dataset_summary() -> DatasetSummaryDTO:
        return _dataset_summary(rt)

    @router.get("/dataset/items", response_model=DatasetItemsResponse)
    def dataset_items(
        limit: Annotated[int, Query(ge=1, le=500)] = 80,
        offset: Annotated[int, Query(ge=0)] = 0,
        source: str | None = None,
        cls_name: str | None = None,
        trusted: bool | None = None,
        search: str | None = None,
    ) -> DatasetItemsResponse:
        catalog = DatasetCatalog(rt.dataset_file)
        try:
            rows, total = catalog.list_items(
                limit=limit,
                offset=offset,
                source=source,
                cls_name=cls_name,
                trusted=trusted,
                search=search,
            )
        finally:
            catalog.close()
        return DatasetItemsResponse(rows=[_dataset_item_to_dto(row) for row in rows], total=total)

    @router.get("/dataset/items/{item_id}", response_model=DatasetAnnotationResponse)
    def dataset_item(item_id: str) -> DatasetAnnotationResponse:
        catalog = DatasetCatalog(rt.dataset_file)
        try:
            row = catalog.get_item(item_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Dataset item not found")
            boxes = catalog.list_boxes(item_id)
        finally:
            catalog.close()
        return DatasetAnnotationResponse(
            item=_dataset_item_to_dto(row),
            boxes=[_dataset_box_to_dto(box) for box in boxes],
        )

    @router.get("/dataset/items/{item_id}/image")
    def dataset_item_image(item_id: str) -> FileResponse:
        catalog = DatasetCatalog(rt.dataset_file)
        try:
            row = catalog.get_item(item_id)
        finally:
            catalog.close()
        if row is None:
            raise HTTPException(status_code=404, detail="Dataset item not found")
        image_path = Path(str(row.get("image_path") or ""))
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Dataset image not found")
        return FileResponse(image_path)

    @router.put("/dataset/items/{item_id}/boxes", response_model=DatasetAnnotationResponse)
    def dataset_item_boxes(item_id: str, payload: AnnotationRequest) -> DatasetAnnotationResponse:
        changed = save_item_annotations(
            item_id,
            [box.model_dump(mode="json") for box in payload.boxes],
            catalog_path=rt.dataset_file,
        )
        if changed == 0:
            raise HTTPException(status_code=404, detail="Dataset item not found or not writable")
        rt.refresh_manual_references()
        catalog = DatasetCatalog(rt.dataset_file)
        try:
            row = catalog.get_item(item_id)
            boxes = catalog.list_boxes(item_id)
        finally:
            catalog.close()
        if row is None:
            raise HTTPException(status_code=404, detail="Dataset item not found")
        return DatasetAnnotationResponse(
            item=_dataset_item_to_dto(row),
            boxes=[_dataset_box_to_dto(box) for box in boxes],
        )

    @router.post("/dataset/sync", response_model=ActionResult)
    def dataset_sync() -> ActionResult:
        queue_dir = _queue_dir(rt)
        catalog = DatasetCatalog(rt.dataset_file)
        try:
            indexed = catalog.index_queue(queue_dir)
        finally:
            catalog.close()
        return ActionResult(ok=True, message="Dataset catalog synced", count=indexed)

    @router.post("/dataset/import", response_model=ActionResult)
    async def dataset_import(
        file: Annotated[UploadFile, File()],
        source_name: Annotated[str, Form()] = "roboflow",
    ) -> ActionResult:
        suffix = Path(file.filename or "dataset.zip").suffix or ".zip"
        tmp = Path(tempfile.mkdtemp(prefix="trash_sorter_import_"))
        zip_path = tmp / f"upload{suffix}"
        clean_source = _clean_source_name(source_name)
        class_map = {name: cls_id for cls_id, name in rt.model_classes().items()}
        try:
            with zip_path.open("wb") as f:
                shutil.copyfileobj(file.file, f)
            imported = import_yolo_dataset_to_queue(
                zip_path,
                _queue_dir(rt),
                source_name=clean_source,
                class_name_to_id=class_map,
                catalog_path=rt.dataset_file,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return ActionResult(ok=True, message="Roboflow/YOLO import completed", count=imported)

    @router.post("/dataset/manual", response_model=ActionResult)
    async def dataset_manual(
        files: Annotated[list[UploadFile], File()],
        cls_name: Annotated[str, Form()],
        cls_id: Annotated[int, Form()] = 0,
    ) -> ActionResult:
        class_name = canonical_class_name(cls_name)
        if not class_name:
            raise HTTPException(status_code=400, detail="cls_name is required")
        tmp = Path(tempfile.mkdtemp(prefix="trash_sorter_manual_"))
        saved: list[str] = []
        try:
            for upload in files:
                name = Path(upload.filename or "image.jpg").name
                out = tmp / name
                with out.open("wb") as f:
                    shutil.copyfileobj(upload.file, f)
                saved.append(str(out))
            added = import_manual_images(
                saved,
                _queue_dir(rt),
                class_name,
                _manual_class_id(class_name, cls_id),
                catalog_path=rt.dataset_file,
            )
            if added:
                _ensure_manual_class_mapping(rt, class_name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return ActionResult(ok=True, message="Manual images imported", count=added)

    @router.post("/dataset/camera-sample", response_model=ActionResult)
    def dataset_camera_sample(payload: CameraSampleRequest) -> ActionResult:
        class_name = canonical_class_name(payload.cls_name)
        if not class_name:
            raise HTTPException(status_code=400, detail="cls_name is required")
        _ensure_manual_class_mapping(rt, class_name)
        try:
            img_path = rt.capture_camera_sample(
                class_name,
                _manual_class_id(class_name, payload.cls_id),
                use_latest_detection_box=payload.use_latest_detection_box,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return ActionResult(ok=True, message=f"Camera sample saved: {img_path.name}", count=1)

    @router.post("/dataset/capture-session/start", response_model=CaptureSessionResponse)
    def dataset_capture_session_start(
        payload: CaptureSessionStartRequest,
    ) -> CaptureSessionResponse:
        class_name = canonical_class_name(payload.cls_name)
        if not class_name:
            raise HTTPException(status_code=400, detail="cls_name is required")
        _ensure_manual_class_mapping(rt, class_name)
        try:
            state = rt.start_capture_session(
                class_name,
                _manual_class_id(class_name, payload.cls_id),
                target_count=payload.target_count,
                holdout_count=payload.holdout_count,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return CaptureSessionResponse(**state)

    @router.get("/dataset/capture-session", response_model=CaptureSessionResponse)
    def dataset_capture_session_status() -> CaptureSessionResponse:
        return CaptureSessionResponse(**rt.capture_session_status())

    @router.post("/dataset/capture-session/capture", response_model=CaptureSessionResponse)
    def dataset_capture_session_frame(
        payload: CaptureSessionFrameRequest,
    ) -> CaptureSessionResponse:
        try:
            state = rt.capture_session_frame(
                pose_index=payload.pose_index,
                use_latest_detection_box=payload.use_latest_detection_box,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return CaptureSessionResponse(**state)

    @router.post("/dataset/capture-session/stop", response_model=CaptureSessionResponse)
    def dataset_capture_session_stop() -> CaptureSessionResponse:
        return CaptureSessionResponse(**rt.stop_capture_session())

    @router.post("/dataset/manual-url", response_model=ActionResult)
    def dataset_manual_url(payload: ManualUrlImportRequest) -> ActionResult:
        class_name = canonical_class_name(payload.cls_name)
        if not class_name:
            raise HTTPException(status_code=400, detail="cls_name is required")
        urls = [url.strip() for url in payload.urls if url.strip()]
        if not urls:
            raise HTTPException(status_code=400, detail="At least one image URL is required")
        source_page_url = payload.source_page_url.strip()
        source_license = payload.source_license.strip()
        if not source_page_url or not source_license:
            raise HTTPException(
                status_code=400,
                detail="Web image import requires source_page_url and source_license",
            )
        _ensure_manual_class_mapping(rt, class_name)
        try:
            added = import_manual_image_urls(
                urls,
                _queue_dir(rt),
                class_name,
                _manual_class_id(class_name, payload.cls_id),
                source_page_url=source_page_url,
                source_license=source_license,
                source_author=payload.source_author.strip(),
                catalog_path=rt.dataset_file,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not added:
            raise HTTPException(status_code=400, detail="No image URLs were imported")
        return ActionResult(ok=True, message=f"Manual URL images imported: {added}", count=added)

    @router.post("/dataset/relabel", response_model=ActionResult)
    def dataset_relabel(payload: RelabelRequest) -> ActionResult:
        class_name = canonical_class_name(payload.cls_name)
        class_id = default_class_id_for_name(class_name)
        if class_id is None:
            class_id = payload.cls_id
        _ensure_manual_class_mapping(rt, class_name)
        changed = relabel_images(
            [Path(p) for p in payload.image_paths],
            class_name,
            class_id,
            catalog_path=rt.dataset_file,
        )
        return ActionResult(ok=True, message="Images relabeled", count=changed)

    @router.post("/dataset/delete", response_model=ActionResult)
    def dataset_delete(payload: DeleteRequest) -> ActionResult:
        removed = delete_queue_items([Path(p) for p in payload.image_paths], catalog_path=rt.dataset_file)
        return ActionResult(ok=True, message="Images deleted", count=removed)

    @router.post("/dataset/bulk", response_model=ActionResult)
    def dataset_bulk(payload: BulkDatasetRequest) -> ActionResult:
        image_paths = [Path(p) for p in payload.image_paths]
        if payload.action == "delete":
            count = delete_queue_items(image_paths, catalog_path=rt.dataset_file)
            return ActionResult(ok=True, message="Bulk delete completed", count=count)
        if payload.action == "quarantine":
            count = quarantine_queue_items(image_paths, catalog_path=rt.dataset_file)
            return ActionResult(ok=True, message="Bulk quarantine completed", count=count)
        if payload.action == "mark_trusted":
            count = mark_items_trusted(image_paths, trusted=True, catalog_path=rt.dataset_file)
            return ActionResult(ok=True, message="Items marked trusted", count=count)
        if payload.action == "mark_untrusted":
            count = mark_items_trusted(image_paths, trusted=False, catalog_path=rt.dataset_file)
            return ActionResult(ok=True, message="Items marked untrusted", count=count)
        if payload.cls_name is None or payload.cls_id is None:
            raise HTTPException(status_code=400, detail="cls_name and cls_id are required for relabel")
        class_name = canonical_class_name(payload.cls_name)
        class_id = default_class_id_for_name(class_name)
        if class_id is None:
            class_id = payload.cls_id
        _ensure_manual_class_mapping(rt, class_name)
        count = relabel_images(
            image_paths,
            class_name,
            class_id,
            catalog_path=rt.dataset_file,
        )
        return ActionResult(ok=True, message="Bulk relabel completed", count=count)

    @router.post("/dataset/quarantine", response_model=ActionResult)
    def dataset_quarantine() -> ActionResult:
        moved = quarantine_untrusted_items(_queue_dir(rt), catalog_path=rt.dataset_file)
        return ActionResult(ok=True, message="Untrusted data quarantined", count=moved)

    @router.get("/logs")
    def logs(limit: Annotated[int, Query(ge=1, le=1000)] = 200) -> dict:
        return {"lines": _read_log_lines(limit)}

    app.include_router(user_router)
    app.include_router(router)

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket) -> None:
        auth_header = websocket.headers.get("authorization", "")
        query_token = websocket.query_params.get("token", "")
        try:
            context = authenticate_token_values(
                authorization=auth_header,
                query_token=query_token,
            )
        except HTTPException:
            await websocket.close(code=1008)
            return
        if context.role != "admin":
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(rt.live_payload())
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return

    return app


def _queue_dir(runtime: AgentRuntime) -> Path:
    return Path(runtime.cfg.capture.output_dir) / "low_conf_queue"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _require_stream_token(query_token: str | None) -> None:
    context = authenticate_token_values(query_token=query_token)
    if context.role == "admin":
        return
    raise HTTPException(status_code=403, detail="Admin access required")


def _training_status(root: Path) -> TrainingStatusDTO:
    processes = _training_processes()
    run_name = _active_training_run(processes)
    if not run_name:
        run_name = _latest_training_run(root)

    if not run_name:
        return TrainingStatusDTO(message="Chưa có run huấn luyện nào.")

    run_dir = root / "runs" / "train" / run_name
    args = _read_simple_yaml(run_dir / "args.yaml")
    results_path = run_dir / "results.csv"
    latest = _latest_csv_row(results_path)
    segment_epoch = _int_or_none(latest.get("epoch")) + 1 if latest else None
    segment_epochs = _int_or_none(args.get("epochs"))
    if segment_epoch is not None and segment_epochs is not None:
        segment_epoch = min(segment_epoch, segment_epochs)
    offset = _resume_epoch_offset(root, str(args.get("model") or ""))
    completed_epoch = offset + segment_epoch if segment_epoch is not None else None
    target_epoch = offset + segment_epochs if segment_epochs is not None else None
    if completed_epoch is not None and target_epoch is not None:
        completed_epoch = min(completed_epoch, target_epoch)
    progress = (
        min(100.0, round((completed_epoch / target_epoch) * 100, 1))
        if completed_epoch is not None and target_epoch
        else 0.0
    )
    log_path = _latest_training_log(root, run_name)
    best_model = run_dir / "weights" / "best.pt"
    last_model = run_dir / "weights" / "last.pt"
    running = bool(processes)
    if completed_epoch is not None and target_epoch is not None:
        message = f"Đang chạy {completed_epoch}/{target_epoch}" if running else f"Đã dừng ở {completed_epoch}/{target_epoch}"
    else:
        message = "Đang huấn luyện" if running else "Training đang tắt"

    return TrainingStatusDTO(
        running=running,
        run_name=run_name,
        log_path=str(log_path) if log_path else "",
        results_path=str(results_path) if results_path.exists() else "",
        best_model_path=str(best_model) if best_model.exists() else "",
        last_model_path=str(last_model) if last_model.exists() else "",
        segment_epoch=segment_epoch,
        segment_epochs=segment_epochs,
        completed_epoch=completed_epoch,
        target_epoch=target_epoch,
        progress_percent=progress,
        precision=_float_or_none(latest.get("metrics/precision(B)") if latest else None),
        recall=_float_or_none(latest.get("metrics/recall(B)") if latest else None),
        map50=_float_or_none(latest.get("metrics/mAP50(B)") if latest else None),
        map5095=_float_or_none(latest.get("metrics/mAP50-95(B)") if latest else None),
        message=message,
    )


def _training_processes() -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -like '*scripts\\train_yolo.py*' "
        "-and $_.CommandLine -notlike '*Where-Object*scripts\\train_yolo.py*' } | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3"
    )
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = res.stdout.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _active_training_run(processes: list[dict[str, object]]) -> str:
    for process in processes:
        command = str(process.get("CommandLine") or "")
        marker = "--name"
        parts = command.split()
        for index, part in enumerate(parts):
            if part == marker and index + 1 < len(parts):
                return parts[index + 1].strip("\"'")
    return ""


def _latest_training_run(root: Path) -> str:
    train_dir = root / "runs" / "train"
    if not train_dir.exists():
        return ""
    candidates = [path for path in train_dir.iterdir() if (path / "results.csv").exists()]
    if not candidates:
        return ""
    latest = max(candidates, key=lambda path: (path / "results.csv").stat().st_mtime)
    return latest.name


def _latest_training_log(root: Path, run_name: str) -> Path | None:
    log_dir = root / "runs" / "train_logs"
    if not log_dir.exists():
        return None
    files = sorted(log_dir.glob(f"{run_name}-*.log"), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def _latest_csv_row(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return {}
    return dict(rows[-1]) if rows else {}


def _read_simple_yaml(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _resume_epoch_offset(root: Path, model_path: str) -> int:
    normalized = model_path.replace("/", os.sep)
    markers = [f"{os.sep}runs{os.sep}train{os.sep}", f"runs{os.sep}train{os.sep}"]
    marker = next((item for item in markers if item in normalized), "")
    if not marker:
        return 0
    tail = normalized.split(marker, 1)[1]
    previous_run = tail.split(os.sep, 1)[0]
    latest = _latest_csv_row(root / "runs" / "train" / previous_run / "results.csv")
    epoch = _int_or_none(latest.get("epoch"))
    return epoch + 1 if epoch is not None else 0


def _int_or_none(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _clean_mappings(mappings: list[ClassMapping]) -> list[ClassMapping]:
    cleaned: list[ClassMapping] = []
    for mapping in mappings:
        class_name = mapping.class_name.strip()
        command = mapping.command.strip().upper()
        if not class_name:
            raise HTTPException(status_code=422, detail="Class name không được rỗng")
        if len(command) != 1:
            raise HTTPException(status_code=422, detail="Command UART phải đúng 1 ký tự")
        cleaned.append(
            mapping.model_copy(
                update={
                    "class_name": class_name,
                    "command": command,
                    "bin_index": int(mapping.bin_index),
                }
            )
        )
    return cleaned


def _ensure_manual_class_mapping(runtime: AgentRuntime, cls_name: str) -> None:
    class_name = canonical_class_name(cls_name)
    if not class_name:
        raise HTTPException(status_code=422, detail="Class name is required")
    existing = {mapping.class_name.strip().casefold() for mapping in runtime.cfg.mappings}
    if class_name.casefold() in existing:
        return
    category = category_for_class(class_name)
    runtime.update_mappings(
        [
            *runtime.cfg.mappings,
            ClassMapping(
                class_name=class_name,
                command=category.code,
                bin_index=category.bin_index,
                enabled=True,
            ),
        ]
    )


def _manual_class_id(class_name: str, fallback: int) -> int:
    known = default_class_id_for_name(class_name)
    return int(fallback) if known is None else known


def _dataset_summary(runtime: AgentRuntime) -> DatasetSummaryDTO:
    queue_dir = _queue_dir(runtime)
    catalog = DatasetCatalog(runtime.dataset_file)
    try:
        catalog_total = catalog.count_total()
        by_source = catalog.count_by_source()
        by_trusted = catalog.count_by_trusted()
        box_catalog_total = catalog.count_boxes_total()
        box_classes = catalog.count_box_classes()
        class_catalog_total = catalog.count_distinct_box_classes()
    finally:
        catalog.close()

    queue_images = _count_queue_images(queue_dir)
    if catalog_total > 0 and box_catalog_total > 0:
        sources = _dataset_sources(by_source)
        out_of_sync = catalog_total != queue_images
        return DatasetSummaryDTO(
            images=catalog_total,
            boxes=box_catalog_total,
            classes=box_classes,
            sources=sources,
            catalog_total=catalog_total,
            box_catalog_total=box_catalog_total,
            class_catalog_total=class_catalog_total,
            trainable_total=by_trusted["trainable"],
            needs_review_total=by_trusted["needs_review"],
            out_of_sync=out_of_sync,
            needs_sync=out_of_sync,
            missing_meta=0,
            queue_dir=str(queue_dir.resolve()),
            catalog_path=str(runtime.dataset_file.resolve()),
        )

    summary = summarize_queue(queue_dir)
    json_boxes = int(summary["boxes"])
    classes = (
        box_classes
        if box_catalog_total > 0 and box_catalog_total == json_boxes
        else {str(name): int(count) for name, count in summary["classes"].items()}
    )
    sources = {
        "roboflow": int(summary["roboflow"]),
        "manual_import": int(summary["manual"]),
        "manual_camera_capture": int(summary["sources"].get("manual_camera_capture", 0)),
        "manual_web_import": int(summary["sources"].get("manual_web_import", 0)),
        "auto_low_conf": int(summary["auto"]),
        "unknown": int(summary["unknown"]),
        "untrusted": int(summary["untrusted"]),
    }
    for key, value in by_source.items():
        sources.setdefault(key, value)
    out_of_sync = catalog_total != int(summary["images"])
    needs_sync = out_of_sync or box_catalog_total != json_boxes
    return DatasetSummaryDTO(
        images=int(summary["images"]),
        boxes=json_boxes,
        classes=classes,
        sources=sources,
        catalog_total=catalog_total,
        box_catalog_total=box_catalog_total,
        class_catalog_total=class_catalog_total,
        trainable_total=by_trusted["trainable"],
        needs_review_total=by_trusted["needs_review"],
        out_of_sync=out_of_sync,
        needs_sync=needs_sync,
        missing_meta=int(summary["missing_meta"]),
        queue_dir=str(_queue_dir(runtime).resolve()),
        catalog_path=str(runtime.dataset_file.resolve()),
    )


def _count_queue_images(queue_dir: Path) -> int:
    if not queue_dir.exists():
        return 0
    return sum(1 for _ in queue_dir.glob("*.jpg"))


def _dataset_sources(by_source: dict[str, int]) -> dict[str, int]:
    sources = {
        "roboflow": 0,
        "manual_import": 0,
        "manual_camera_capture": 0,
        "manual_web_import": 0,
        "auto_low_conf": 0,
        "unknown": 0,
        "untrusted": 0,
    }
    for key, value in by_source.items():
        sources[key] = int(value)
    return sources


def _clean_source_name(source_name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in source_name.strip())
    return cleaned[:48] or "roboflow"


def _dataset_item_to_dto(row: dict) -> DatasetItemDTO:
    source = str(row.get("source") or "unknown")
    reviewed = bool(row.get("reviewed"))
    trusted = bool(row.get("trusted", source not in {"unknown", "untrusted"}))
    meta_path = Path(str(row.get("meta_path") or ""))
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            reviewed = bool(meta.get("reviewed")) if isinstance(meta, dict) else reviewed
            trusted = is_trusted_meta(meta if isinstance(meta, dict) else {})
            if isinstance(meta, dict) and source == "auto_low_conf" and not meta.get("reviewed"):
                trusted = False
        except (OSError, json.JSONDecodeError):
            trusted = False
    return DatasetItemDTO(
        item_id=str(row.get("item_id") or ""),
        image_path=str(row.get("image_path") or ""),
        meta_path=str(row.get("meta_path") or ""),
        source=source,
        cls_id=row.get("cls_id"),
        cls_name=row.get("cls_name"),
        box_count=int(row.get("box_count") or 0),
        width=row.get("width"),
        height=row.get("height"),
        split=row.get("split"),
        original_file=row.get("original_file"),
        ts=row.get("ts"),
        updated_at=str(row.get("updated_at") or ""),
        trusted=trusted,
        reviewed=reviewed,
    )


def _dataset_box_to_dto(row: dict) -> DatasetBoxDTO:
    return DatasetBoxDTO(
        cls_id=int(row.get("cls_id") or 0),
        cls_name=str(row.get("cls_name") or ""),
        conf=float(row.get("conf") or 1.0),
        xyxy=(
            float(row.get("x1") or 0.0),
            float(row.get("y1") or 0.0),
            float(row.get("x2") or 0.0),
            float(row.get("y2") or 0.0),
        ),
    )


def _history_row_to_dto(row) -> HistoryRowDTO:
    return HistoryRowDTO(
        id=int(row.id),
        track_id=int(row.track_id),
        ts=str(row.ts),
        cls_id=int(row.cls_id),
        cls_name=str(row.cls_name),
        conf=float(row.conf),
        bbox=(row.bbox_x1, row.bbox_y1, row.bbox_x2, row.bbox_y2),
        image_path=getattr(row, "image_path", None),
        annotated_path=getattr(row, "annotated_path", None),
        meta_path=getattr(row, "meta_path", None),
        route_label=getattr(row, "route_label", None),
        bin_index=getattr(row, "bin_index", None),
        uart_command=row.uart_command,
        ack_status=row.ack_status,
        rtt_ms=row.rtt_ms,
    )


def _read_log_lines(limit: int) -> list[str]:
    files = sorted(logs_dir().glob("*.log"), key=os.path.getmtime)
    if not files:
        return []
    try:
        raw_lines = files[-1].read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [_format_log_line(line) for line in raw_lines[-limit:]]


def _format_log_line(line: str) -> str:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return line
    text = data.get("text") if isinstance(data, dict) else None
    if isinstance(text, str) and text.strip():
        return text.rstrip()
    record = data.get("record") if isinstance(data, dict) else None
    if isinstance(record, dict):
        time = record.get("time")
        level = record.get("level")
        message = str(record.get("message") or "").strip()
        when = str(time.get("repr") or "") if isinstance(time, dict) else ""
        level_name = str(level.get("name") or "") if isinstance(level, dict) else ""
        parts = [part for part in (when[:23], level_name, message) if part]
        if parts:
            return " | ".join(parts)
    return line


__all__ = ["create_app"]

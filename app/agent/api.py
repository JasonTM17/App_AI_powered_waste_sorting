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
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy.exc import IntegrityError

from app.agent.ai_chat_service import (
    DEFAULT_ADMIN_PROFILE,
    DEFAULT_USER_PROFILE,
    build_chat_response,
)
from app.agent.auth import (
    AuthContext,
    authenticate_token_values,
    extract_token,
    require_active_admin_token,
    require_active_user_token,
    require_user_token,
)
from app.agent.auth_password_policy import PasswordPolicyError
from app.agent.auth_rate_limit import LoginRateLimiter
from app.agent.auth_service import (
    USER_CHAT_MONTHLY_LIMIT,
    AuthService,
    ChatQuota,
    InactiveAccountError,
)
from app.agent.chat_knowledge_service import (
    evaluate_knowledge_retrieval,
    list_knowledge_entries,
    patch_knowledge_entry,
    reload_knowledge_entries,
    retrieve_knowledge_snippets,
    upsert_knowledge_entry,
)
from app.agent.operations_store import OperationsStore
from app.agent.runtime import STREAM_FRAME_INTERVAL_S, AgentRuntime
from app.agent.schemas import (
    AccountCreateRequest,
    AccountDTO,
    AccountPasswordResetRequest,
    AccountPatchRequest,
    AccountsResponse,
    ActionResult,
    ActuationTestModeRequest,
    ActuationTestModeResponse,
    AiChatRequest,
    AiChatResponse,
    AlertPatchRequest,
    AlertsResponse,
    AnnotationRequest,
    AuthChangePasswordRequest,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthLogoutResponse,
    AuthMeResponse,
    BinMapResponse,
    BinStationCreateRequest,
    BinStationDTO,
    BinStationPatchRequest,
    BulkDatasetRequest,
    CameraSampleRequest,
    CaptureSessionFrameRequest,
    CaptureSessionResponse,
    CaptureSessionStartRequest,
    CollectionCompleteRequest,
    CollectionCompleteResponse,
    CollectionSchedulesResponse,
    CommonWasteCatalogResponse,
    DatasetAnnotationResponse,
    DatasetBoxDTO,
    DatasetItemDTO,
    DatasetItemsResponse,
    DatasetSummaryDTO,
    DeleteRequest,
    DeviceIssueCreateRequest,
    DeviceIssueResponse,
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
    KnowledgeCatalogResponse,
    KnowledgeEntryDTO,
    KnowledgeEntryPatchRequest,
    KnowledgeEntryUpsertRequest,
    KnowledgeEvaluateRequest,
    KnowledgeEvaluateResponse,
    KnowledgeScoreDTO,
    LearnNowStatusResponse,
    LearnNowTrainRequest,
    ManualUrlImportRequest,
    MappingsResponse,
    ModelClassesResponse,
    OperationDeviceDTO,
    OperationDevicesResponse,
    OperationDeviceUpsertRequest,
    OperationsHealthResponse,
    RelabelRequest,
    RoleCatalogResponse,
    RuntimeStatus,
    ServoAngleTestRequest,
    ServoAngleTestResponse,
    SettingsResponse,
    SortAngleTestRequest,
    SourceQualityResponse,
    TrainingStatusDTO,
    UnknownLearnRequest,
    UnknownLearnResponse,
    UserAdvisorRequest,
    UserAdvisorResponse,
    UserAnalyticsResponse,
    UserDashboardResponse,
    UserDeviceResponse,
    UserExperienceResponse,
    UserHistoryResponse,
    UserReportResponse,
    WebSourceDiscoveryRequest,
    WebSourceDiscoveryResponse,
)
from app.agent.user_dashboard import (
    build_user_advisor,
    build_user_analytics,
    build_user_dashboard,
    build_user_history,
)
from app.agent.user_screen_experience import (
    build_user_device,
    build_user_experience,
    build_user_history_export_csv,
    build_user_report,
)
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
from app.core.learn_now import build_learn_now_status
from app.core.licensed_source_ingestion import validate_manual_url_source
from app.core.source_quality_report import build_source_quality_report
from app.core.vision_label_provider import suggest_unknown_labels
from app.core.waste_categories import (
    canonical_class_name,
    category_for_class,
    default_class_id_for_name,
)
from app.core.web_source_discovery import discover_web_sources
from app.utils.dataset_import import import_yolo_dataset_to_queue
from app.utils.paths import config_path, dataset_db_path, db_path, logs_dir

ALLOWED_ORIGINS_ENV = "TRASH_SORTER_ALLOWED_ORIGINS"
_login_limiter = LoginRateLimiter()


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

    app = FastAPI(title="Trash Sorter Pro Agent", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.runtime = rt

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    auth_router = APIRouter(prefix="/api")

    @auth_router.post("/auth/login", response_model=AuthLoginResponse)
    def login(payload: AuthLoginRequest, request: Request) -> AuthLoginResponse:
        key = _login_key(request, payload.username)
        if _login_limiter.is_limited(key):
            raise HTTPException(status_code=429, detail="Too many login attempts")
        service = AuthService()
        if not service.has_accounts():
            raise HTTPException(status_code=503, detail="Account login is not configured")
        try:
            result = service.login(
                payload.username,
                payload.password,
                client_label=_client_label(request),
            )
        except InactiveAccountError:
            _login_limiter.record_failure(key)
            raise HTTPException(status_code=403, detail="Account is disabled") from None
        if result is None:
            _login_limiter.record_failure(key)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        _login_limiter.reset(key)
        identity = result.identity
        return AuthLoginResponse(
            token=result.token,
            role=identity.role,
            account_id=identity.account_id,
            username=identity.username,
            capabilities=AuthContext(
                role=identity.role,
                auth_required=True,
                account_id=identity.account_id,
                username=identity.username,
                token_source="session",
                session_expires_at=identity.expires_at,
                password_default=identity.password_default,
            ).capabilities,
            expires_at=identity.expires_at,
            password_default=identity.password_default,
        )

    @auth_router.post("/auth/logout", response_model=AuthLogoutResponse)
    def logout(
        authorization: Annotated[str | None, Header()] = None,
        token: Annotated[str | None, Query()] = None,
    ) -> AuthLogoutResponse:
        AuthService().revoke_session(extract_token(authorization, token))
        return AuthLogoutResponse(message="Da dang xuat")

    @auth_router.post("/auth/change-password", response_model=AuthMeResponse)
    def change_password(
        payload: AuthChangePasswordRequest,
        context: Annotated[AuthContext, Depends(require_user_token)],
        authorization: Annotated[str | None, Header()] = None,
        token: Annotated[str | None, Query()] = None,
    ) -> AuthMeResponse:
        if context.account_id is None or context.token_source != "session":
            raise HTTPException(status_code=403, detail="Session login required")
        raw_token = extract_token(authorization, token)
        try:
            changed = AuthService().change_password(
                account_id=context.account_id,
                current_password=payload.current_password,
                new_password=payload.new_password,
                current_token=raw_token,
            )
        except PasswordPolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not changed:
            raise HTTPException(status_code=401, detail="Current password is invalid")
        updated = authenticate_token_values(authorization=authorization, query_token=token)
        return _auth_me_response(updated)

    user_router = APIRouter(prefix="/api")

    @user_router.get("/me", response_model=AuthMeResponse)
    def me(context: Annotated[AuthContext, Depends(require_user_token)]) -> AuthMeResponse:
        return _auth_me_response(context)

    @user_router.get("/user/dashboard", response_model=UserDashboardResponse)
    def user_dashboard(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> UserDashboardResponse:
        return build_user_dashboard(rt, **_owner_scope(context))

    @user_router.get("/user/analytics", response_model=UserAnalyticsResponse)
    def user_analytics(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        range_days: Annotated[int, Query()] = 30,
    ) -> UserAnalyticsResponse:
        return build_user_analytics(rt, range_days, **_owner_scope(context))

    @user_router.get("/user/device", response_model=UserDeviceResponse)
    def user_device(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> UserDeviceResponse:
        return build_user_device(rt, **_owner_scope(context))

    @user_router.get("/user/report", response_model=UserReportResponse)
    def user_report(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        range_days: Annotated[int, Query()] = 30,
    ) -> UserReportResponse:
        return build_user_report(rt, range_days, **_owner_scope(context))

    @user_router.get("/user/experience", response_model=UserExperienceResponse)
    def user_experience(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        range_days: Annotated[int, Query()] = 30,
    ) -> UserExperienceResponse:
        return build_user_experience(rt, range_days, **_owner_scope(context))

    @user_router.get("/user/history", response_model=UserHistoryResponse)
    def user_history(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> UserHistoryResponse:
        return build_user_history(rt, **_owner_scope(context), limit=limit, offset=offset)

    @user_router.get("/user/history/export.csv")
    def user_history_export_csv(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        range_days: Annotated[int, Query()] = 30,
    ) -> Response:
        csv_text = build_user_history_export_csv(rt, range_days, **_owner_scope(context))
        return Response(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=trash-sorter-user-history.csv"
            },
        )

    @user_router.get("/user/history/{row_id}/image")
    def user_history_image(
        row_id: int,
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        kind: Annotated[Literal["annotated", "raw"], Query()] = "annotated",
    ) -> FileResponse:
        service = HistoryService(rt.history_file)
        try:
            row = service.get(row_id, **_owner_scope(context))
        finally:
            service.close()
        if row is None:
            raise HTTPException(status_code=404, detail="History row not found")
        path_value = _history_image_path_value(row, kind)
        if not path_value:
            raise HTTPException(status_code=404, detail="Detection image not found")
        image_path = Path(path_value)
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Detection image not found")
        return FileResponse(image_path)

    @user_router.post("/user/advisor", response_model=UserAdvisorResponse)
    def user_advisor(
        payload: UserAdvisorRequest,
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> UserAdvisorResponse:
        quota = _consume_user_chat_quota(context)
        if quota and quota.exceeded:
            return _user_advisor_quota_response(payload.range_days, quota)
        response = build_user_advisor(
            rt,
            range_days=payload.range_days,
            question=payload.question,
            **_owner_scope(context),
        )
        return _attach_quota(response, quota)

    @user_router.post("/user/chat", response_model=AiChatResponse)
    def user_chat(
        payload: AiChatRequest,
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> AiChatResponse:
        quota = _consume_user_chat_quota(context)
        if quota and quota.exceeded:
            return _user_chat_quota_response(quota)
        analytics = build_user_analytics(rt, 30, **_owner_scope(context))
        chat_context = _analytics_chat_context(analytics)
        chat_context["operations"] = _operations_summary_context(rt, owner_username=context.username)
        response = build_chat_response(
            role="user",
            message=payload.message,
            context=chat_context,
            profile=DEFAULT_USER_PROFILE,
            knowledge_snippets=retrieve_knowledge_snippets(
                role="user",
                question=payload.message,
                context=chat_context,
            ),
            conversation_style="Ngắn gọn, thân thiện, giải thích bằng dữ liệu trong dashboard User.",
        )
        return _attach_quota(response, quota)

    @user_router.get("/user/bin-map", response_model=BinMapResponse)
    def user_bin_map(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> BinMapResponse:
        store = _operations_store(rt)
        try:
            return BinMapResponse(**store.list_bin_map(owner_username=context.username))
        finally:
            store.close()

    @user_router.get("/user/alerts", response_model=AlertsResponse)
    def user_alerts(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
        include_resolved: Annotated[bool, Query()] = True,
    ) -> AlertsResponse:
        store = _operations_store(rt)
        try:
            rows = store.list_alerts(
                owner_username=context.username,
                include_resolved=include_resolved,
            )
            return AlertsResponse(alerts=rows, total=len(rows))
        finally:
            store.close()

    @user_router.get("/user/collection-schedule", response_model=CollectionSchedulesResponse)
    def user_collection_schedule(
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> CollectionSchedulesResponse:
        store = _operations_store(rt)
        try:
            rows = store.list_schedules(owner_username=context.username)
            return CollectionSchedulesResponse(schedules=rows, total=len(rows))
        finally:
            store.close()

    @user_router.post(
        "/user/collections/{schedule_id}/complete",
        response_model=CollectionCompleteResponse,
    )
    def user_complete_collection(
        schedule_id: str,
        payload: CollectionCompleteRequest,
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> CollectionCompleteResponse:
        store = _operations_store(rt)
        try:
            scoped = {
                token
                for row in store.list_schedules(owner_username=context.username)
                for token in (str(row["id"]), str(row["schedule_id"]))
            }
            if schedule_id not in scoped:
                raise HTTPException(status_code=404, detail="Collection schedule not found")
            schedule = store.complete_collection(
                schedule_id,
                actor_username=context.username or "user",
                actor_account_id=context.account_id,
                note=payload.note,
            )
            if schedule is None:
                raise HTTPException(status_code=404, detail="Collection schedule not found")
            already_completed = bool(schedule.pop("already_completed", False))
            return CollectionCompleteResponse(
                schedule=schedule,
                already_completed=already_completed,
            )
        finally:
            store.close()

    @user_router.post("/user/device-issues", response_model=DeviceIssueResponse)
    def user_device_issue(
        payload: DeviceIssueCreateRequest,
        context: Annotated[AuthContext, Depends(require_active_user_token)],
    ) -> DeviceIssueResponse:
        store = _operations_store(rt)
        try:
            if payload.station_id:
                scoped_stations = {
                    station["station_id"]
                    for station in store.list_bin_map(owner_username=context.username)["stations"]
                }
                if payload.station_id not in scoped_stations:
                    raise HTTPException(status_code=404, detail="Bin station not found")
            issue = store.create_issue(
                payload.model_dump(),
                reporter_username=context.username or "user",
                reporter_account_id=context.account_id,
            )
            return DeviceIssueResponse(issue=issue)
        finally:
            store.close()

    router = APIRouter(prefix="/api", dependencies=[Depends(require_active_admin_token)])

    @router.get("/admin/accounts", response_model=AccountsResponse)
    def admin_accounts() -> AccountsResponse:
        return AccountsResponse(accounts=[_account_to_dto(row) for row in AuthService().list_accounts()])

    @router.post("/admin/accounts", response_model=AccountDTO)
    def admin_create_account(payload: AccountCreateRequest) -> AccountDTO:
        service = AuthService()
        try:
            service.create_account(
                payload.username,
                payload.password,
                payload.role,
                password_default=True,
            )
        except PasswordPolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Account already exists or cannot be created") from exc
        return _account_or_404(service, payload.username)

    @router.post("/admin/accounts/{username}/reset-password", response_model=AccountDTO)
    def admin_reset_password(username: str, payload: AccountPasswordResetRequest) -> AccountDTO:
        service = AuthService()
        try:
            changed = service.set_password(
                username,
                payload.password,
                temporary=True,
                revoke_sessions=True,
            )
        except PasswordPolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not changed:
            raise HTTPException(status_code=404, detail="Account not found")
        return _account_or_404(service, username)

    @router.patch("/admin/accounts/{username}", response_model=AccountDTO)
    def admin_patch_account(username: str, payload: AccountPatchRequest) -> AccountDTO:
        service = AuthService()
        if not service.set_active(username, payload.is_active):
            raise HTTPException(status_code=404, detail="Account not found")
        return _account_or_404(service, username)

    @router.post("/admin/history/backfill-owner", response_model=ActionResult)
    def admin_backfill_owner(owner_username: Annotated[str, Query(min_length=1)]) -> ActionResult:
        service = AuthService()
        account = _find_account(service, owner_username)
        if account is None:
            raise HTTPException(status_code=404, detail="Owner account not found")
        history = HistoryService(rt.history_file)
        try:
            count = history.backfill_owner(
                owner_account_id=int(account["id"]),
                owner_username=str(account["username"]),
                device_id=rt.cfg.device.device_id,
            )
        finally:
            history.close()
        return ActionResult(ok=True, message="Legacy history backfilled", count=count)

    @router.get("/admin/roles", response_model=RoleCatalogResponse)
    def admin_roles() -> RoleCatalogResponse:
        store = _operations_store(rt)
        try:
            return RoleCatalogResponse(roles=store.list_role_catalog())
        finally:
            store.close()

    @router.get("/admin/devices", response_model=OperationDevicesResponse)
    def admin_devices() -> OperationDevicesResponse:
        store = _operations_store(rt)
        try:
            return OperationDevicesResponse(devices=store.list_devices())
        finally:
            store.close()

    @router.post("/admin/devices", response_model=OperationDeviceDTO)
    def admin_upsert_device(payload: OperationDeviceUpsertRequest) -> OperationDeviceDTO:
        store = _operations_store(rt)
        try:
            return OperationDeviceDTO(**store.upsert_device(payload.model_dump()))
        finally:
            store.close()

    @router.get("/admin/bin-map", response_model=BinMapResponse)
    def admin_bin_map() -> BinMapResponse:
        store = _operations_store(rt)
        try:
            return BinMapResponse(**store.list_bin_map(include_inactive=True))
        finally:
            store.close()

    @router.post("/admin/bin-map", response_model=BinStationDTO)
    def admin_create_bin_station(payload: BinStationCreateRequest) -> BinStationDTO:
        store = _operations_store(rt)
        try:
            try:
                station = store.create_station(payload.model_dump())
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            return BinStationDTO(**station)
        finally:
            store.close()

    @router.patch("/admin/bin-map/{station_id}", response_model=BinStationDTO)
    def admin_patch_bin_station(
        station_id: str,
        payload: BinStationPatchRequest,
    ) -> BinStationDTO:
        store = _operations_store(rt)
        try:
            station = store.patch_station(station_id, payload.model_dump(exclude_unset=True))
            if station is None:
                raise HTTPException(status_code=404, detail="Bin station not found")
            return BinStationDTO(**station)
        finally:
            store.close()

    @router.delete("/admin/bin-map/{station_id}", response_model=ActionResult)
    def admin_delete_bin_station(station_id: str) -> ActionResult:
        store = _operations_store(rt)
        try:
            if not store.delete_station(station_id):
                raise HTTPException(status_code=404, detail="Bin station not found")
            return ActionResult(ok=True, message="Bin station deactivated", count=1)
        finally:
            store.close()

    @router.get("/admin/alerts", response_model=AlertsResponse)
    def admin_alerts(include_resolved: Annotated[bool, Query()] = True) -> AlertsResponse:
        store = _operations_store(rt)
        try:
            rows = store.list_alerts(include_resolved=include_resolved)
            return AlertsResponse(alerts=rows, total=len(rows))
        finally:
            store.close()

    @router.patch("/admin/alerts/{alert_id}", response_model=AlertsResponse)
    def admin_patch_alert(
        alert_id: str,
        payload: AlertPatchRequest,
        context: Annotated[AuthContext, Depends(require_active_admin_token)],
    ) -> AlertsResponse:
        store = _operations_store(rt)
        try:
            alert = store.patch_alert(
                alert_id,
                status=payload.status,
                actor_username=context.username or "admin",
            )
            if alert is None:
                raise HTTPException(status_code=404, detail="Alert not found")
            rows = store.list_alerts(include_resolved=True)
            return AlertsResponse(alerts=rows, total=len(rows))
        finally:
            store.close()

    @router.get("/admin/collection-schedules", response_model=CollectionSchedulesResponse)
    def admin_collection_schedules() -> CollectionSchedulesResponse:
        store = _operations_store(rt)
        try:
            rows = store.list_schedules()
            return CollectionSchedulesResponse(schedules=rows, total=len(rows))
        finally:
            store.close()

    @router.get("/admin/operations/health", response_model=OperationsHealthResponse)
    def admin_operations_health() -> OperationsHealthResponse:
        store = _operations_store(rt)
        try:
            return OperationsHealthResponse(**store.health())
        finally:
            store.close()

    @router.get("/admin/knowledge", response_model=KnowledgeCatalogResponse)
    def admin_knowledge() -> KnowledgeCatalogResponse:
        return _knowledge_catalog_response(list_knowledge_entries())

    @router.post("/admin/knowledge", response_model=KnowledgeCatalogResponse)
    def admin_upsert_knowledge(payload: KnowledgeEntryUpsertRequest) -> KnowledgeCatalogResponse:
        return _knowledge_catalog_response(upsert_knowledge_entry(payload.model_dump()))

    @router.patch("/admin/knowledge/{entry_id}", response_model=KnowledgeCatalogResponse)
    def admin_patch_knowledge(entry_id: str, payload: KnowledgeEntryPatchRequest) -> KnowledgeCatalogResponse:
        try:
            catalog = patch_knowledge_entry(entry_id, payload.model_dump(exclude_unset=True))
        except KeyError:
            raise HTTPException(status_code=404, detail="Knowledge entry not found") from None
        return _knowledge_catalog_response(catalog)

    @router.post("/admin/knowledge/reload", response_model=KnowledgeCatalogResponse)
    def admin_reload_knowledge() -> KnowledgeCatalogResponse:
        return _knowledge_catalog_response(reload_knowledge_entries())

    @router.post("/admin/knowledge/evaluate", response_model=KnowledgeEvaluateResponse)
    def admin_evaluate_knowledge(payload: KnowledgeEvaluateRequest) -> KnowledgeEvaluateResponse:
        result = evaluate_knowledge_retrieval(role=payload.role, question=payload.question)
        return KnowledgeEvaluateResponse(
            role=result["role"],
            question=result["question"],
            snippets=[_knowledge_snippet_to_dto(item) for item in result["snippets"]],
            scores=[KnowledgeScoreDTO(**item) for item in result["scores"]],
            payload_chars=int(result["payload_chars"]),
        )

    @router.post("/admin/chat", response_model=AiChatResponse)
    def admin_chat(payload: AiChatRequest) -> AiChatResponse:
        chat_context = _admin_chat_context(rt)
        return build_chat_response(
            role="admin",
            message=payload.message,
            context=chat_context,
            profile=DEFAULT_ADMIN_PROFILE,
            knowledge_snippets=retrieve_knowledge_snippets(
                role="admin",
                question=payload.message,
                context=chat_context,
            ),
            conversation_style="Ưu tiên checklist vận hành, nguyên nhân có thể kiểm chứng, và bước tiếp theo an toàn.",
        )

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

    @router.get("/learn-now/status", response_model=LearnNowStatusResponse)
    def learn_now_status(cls_name: str = "") -> LearnNowStatusResponse:
        return LearnNowStatusResponse(**build_learn_now_status(_queue_dir(rt), cls_name))

    @router.get("/dataset/source-quality", response_model=SourceQualityResponse)
    def dataset_source_quality() -> SourceQualityResponse:
        return SourceQualityResponse(**build_source_quality_report(_queue_dir(rt)))

    @router.post("/learn-now/refresh-references", response_model=LearnNowStatusResponse)
    def learn_now_refresh_references(cls_name: str = "") -> LearnNowStatusResponse:
        rt.refresh_manual_references()
        return LearnNowStatusResponse(**build_learn_now_status(_queue_dir(rt), cls_name))

    @router.post("/learn-now/unknown/capture", response_model=UnknownLearnResponse)
    def learn_now_unknown_capture(payload: UnknownLearnRequest) -> UnknownLearnResponse:
        approved_class = canonical_class_name(payload.approved_cls_name)
        if payload.approved_cls_name.strip() and default_class_id_for_name(approved_class) is None:
            raise HTTPException(status_code=400, detail="approved_cls_name must map to a 45-class label")
        class_name = approved_class if approved_class and default_class_id_for_name(approved_class) is not None else "Unknown object"
        class_id = _manual_class_id(class_name, payload.cls_id) if class_name != "Unknown object" else -1
        if class_name != "Unknown object":
            _ensure_manual_class_mapping(rt, class_name)
        try:
            img_path = rt.capture_unknown_learn_sample(class_name, class_id)
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        crop_path = _temporary_dataset_crop(img_path)
        try:
            label_result = suggest_unknown_labels(
                image_path=crop_path or img_path,
                manual_hint=payload.manual_hint,
            )
        finally:
            if crop_path is not None:
                crop_path.unlink(missing_ok=True)
        suggestions = list(label_result.get("suggestions") or [])
        _write_learn_suggestions(rt, img_path, label_result)
        catalog = DatasetCatalog(rt.dataset_file)
        try:
            row = catalog.get_item(img_path.stem)
            boxes = catalog.list_boxes(str(row["item_id"])) if row is not None else []
        finally:
            catalog.close()
        selected = suggestions[0].get("canonical_class") if suggestions and isinstance(suggestions[0], dict) else ""
        status = build_learn_now_status(_queue_dir(rt), str(selected or class_name))
        return UnknownLearnResponse(
            ok=True,
            message=f"Learn capture saved: {img_path.name}. Review bbox before reference/train.",
            provider=str(label_result.get("provider") or ""),
            provider_available=bool(label_result.get("available")),
            hardware_blocked=True,
            item=_dataset_item_to_dto(row) if row is not None else None,
            boxes=[_dataset_box_to_dto(box) for box in boxes],
            suggestions=suggestions,
            learn_status=status.get("selected") if isinstance(status.get("selected"), dict) else None,
        )

    @router.post("/learn-now/micro-train/start", response_model=ActionResult)
    def learn_now_micro_train_start(payload: LearnNowTrainRequest) -> ActionResult:
        class_name = canonical_class_name(payload.cls_name)
        if not class_name:
            raise HTTPException(status_code=400, detail="cls_name is required")
        if rt.actuation_test_mode().get("enabled"):
            raise HTTPException(
                status_code=409,
                detail="Turn Actuation Test Mode off before software training.",
            )
        if _training_processes():
            raise HTTPException(status_code=409, detail="A training process is already running.")
        status = build_learn_now_status(_queue_dir(rt), class_name)
        selected = status.get("selected")
        if not isinstance(selected, dict) or not selected.get("ready_for_micro_train"):
            detail = str(selected.get("message") if isinstance(selected, dict) else "")
            raise HTTPException(
                status_code=409,
                detail=detail or "Need at least 6 reviewed images before micro-train.",
            )
        if payload.profile == "strong" and not selected.get("ready_for_strong_train"):
            raise HTTPException(
                status_code=409,
                detail="Strong train requires at least 24 reviewed images and holdout samples.",
            )
        _ensure_manual_class_mapping(rt, class_name)
        pid = _start_learn_now_training(_project_root(), class_name, payload.profile)
        return ActionResult(
            ok=True,
            message=f"Started {payload.profile} candidate training for {class_name} (pid {pid}).",
            count=1,
        )

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
            "owner_account_id",
            "owner_username",
            "device_id",
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
        path_value = _history_image_path_value(row, kind)
        if not path_value:
            raise HTTPException(status_code=404, detail="Detection image not found")
        image_path = Path(path_value)
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
        source_author = payload.source_author.strip()
        try:
            source_meta = validate_manual_url_source(
                class_name=class_name,
                source_url=urls[0],
                source_page_url=source_page_url,
                source_license=source_license,
                source_author=source_author,
                source_type=payload.source_type,
                generated=payload.generated,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        _ensure_manual_class_mapping(rt, class_name)
        try:
            added = import_manual_image_urls(
                urls,
                _queue_dir(rt),
                class_name,
                _manual_class_id(class_name, payload.cls_id),
                source_page_url=source_page_url,
                source_license=source_license,
                source_author=source_author,
                source_type=str(source_meta["source_type"]),
                generated=bool(source_meta["generated"]),
                extra_meta=source_meta,
                catalog_path=rt.dataset_file,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not added:
            raise HTTPException(status_code=400, detail="No image URLs were imported")
        return ActionResult(ok=True, message=f"Manual URL images imported: {added}", count=added)

    @router.post("/dataset/web-discovery/search", response_model=WebSourceDiscoveryResponse)
    def dataset_web_discovery_search(payload: WebSourceDiscoveryRequest) -> WebSourceDiscoveryResponse:
        class_name = canonical_class_name(payload.cls_name)
        if not class_name or default_class_id_for_name(class_name) is None:
            raise HTTPException(status_code=400, detail="cls_name must map to a 45-class label")
        result = discover_web_sources(cls_name=class_name, query=payload.query, limit=payload.limit)
        return WebSourceDiscoveryResponse(**result)

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

    app.include_router(auth_router)
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
        if context.role != "admin" or context.password_default:
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


def _allowed_origins() -> list[str]:
    raw = os.getenv(ALLOWED_ORIGINS_ENV, "").strip()
    if not raw:
        return ["*"]
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or ["*"]


def _login_key(request: Request, username: str) -> str:
    host = request.client.host if request.client else "local"
    return f"{host}:{username.strip().lower()}"


def _client_label(request: Request) -> str:
    host = request.client.host if request.client else "local"
    agent = request.headers.get("user-agent", "")
    return f"{host} {agent}".strip()


def _auth_me_response(context: AuthContext) -> AuthMeResponse:
    return AuthMeResponse(
        role=context.role,
        capabilities=context.capabilities,
        auth_required=context.auth_required,
        account_id=context.account_id,
        username=context.username,
        token_source=context.token_source,
        session_expires_at=context.session_expires_at,
        password_default=context.password_default,
    )


def _operations_store(runtime: AgentRuntime) -> OperationsStore:
    return OperationsStore(
        runtime.operations_file,
        device_defaults={
            "device_id": runtime.cfg.device.device_id,
            "device_name": runtime.cfg.device.device_name,
            "location": runtime.cfg.device.location,
            "owner_username": runtime.cfg.device.owner_username,
        },
    )


def _owner_scope(context: AuthContext) -> dict[str, object]:
    if context.role == "admin":
        return {"owner_account_id": None, "owner_username": None}
    if context.account_id is not None and context.username:
        return {"owner_account_id": context.account_id, "owner_username": context.username}
    return {"owner_account_id": None, "owner_username": "__session_owner_required__"}


def _consume_user_chat_quota(context: AuthContext) -> ChatQuota | None:
    if context.role != "user" or context.account_id is None:
        return None
    return AuthService().consume_user_chat_quota(context.account_id, limit=USER_CHAT_MONTHLY_LIMIT)


def _attach_quota(response, quota: ChatQuota | None):
    if quota is None:
        return response
    return response.model_copy(update=quota.as_response_fields())


def _user_chat_quota_response(quota: ChatQuota) -> AiChatResponse:
    return AiChatResponse(
        generated_at=datetime.now().isoformat(),
        available=False,
        provider="local",
        model="",
        role="user",
        profile=DEFAULT_USER_PROFILE,
        message=(
            "Bạn đã dùng hết 36 lượt hỏi EcoPet trong tháng này. "
            "EcoPet sẽ mở lại lượt hỏi vào đầu tháng tới; các biểu đồ và lịch sử vẫn dùng bình thường."
        ),
        quick_prompts=[
            "Xem biểu đồ hôm nay",
            "Kiểm tra lịch sử rác",
            "Xem Eco Score",
        ],
        knowledge_used=[],
        safety_notice="",
        **quota.as_response_fields(),
    )


def _user_advisor_quota_response(range_days: int, quota: ChatQuota) -> UserAdvisorResponse:
    clean_range = range_days if range_days in {7, 30, 90, 180} else 30
    return UserAdvisorResponse(
        generated_at=datetime.now().isoformat(),
        available=False,
        provider="local",
        model="",
        profile=DEFAULT_USER_PROFILE,
        range_days=clean_range,  # type: ignore[arg-type]
        message=(
            "Bạn đã dùng hết 36 lượt hỏi EcoPet trong tháng này. "
            "Mình vẫn giữ lại phần biểu đồ, lịch sử và gợi ý có sẵn để bạn theo dõi."
        ),
        local_insights=[],
        knowledge_used=[],
        safety_notice="",
        **quota.as_response_fields(),
    )


def _account_to_dto(row: dict[str, object]) -> AccountDTO:
    role = "admin" if str(row.get("role")) == "admin" else "user"
    return AccountDTO(
        id=int(row.get("id") or 0),
        username=str(row.get("username") or ""),
        role=role,  # type: ignore[arg-type]
        is_active=bool(int(row.get("is_active") or 0)),
        password_default=bool(int(row.get("password_default") or 0)),
        created_at=str(row.get("created_at") or ""),
        last_login_at=str(row.get("last_login_at") or "") or None,
    )


def _find_account(service: AuthService, username: str) -> dict[str, object] | None:
    clean = username.strip()
    for row in service.list_accounts():
        if str(row.get("username") or "") == clean:
            return row
    return None


def _account_or_404(service: AuthService, username: str) -> AccountDTO:
    row = _find_account(service, username)
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return _account_to_dto(row)


def _knowledge_catalog_response(catalog) -> KnowledgeCatalogResponse:
    entries = [_knowledge_entry_to_dto(entry) for entry in catalog.entries]
    return KnowledgeCatalogResponse(
        entries=entries,
        total=len(entries),
        enabled_total=sum(1 for entry in entries if entry.enabled),
        local_path=str(catalog.local_path),
        status=str(catalog.status),
        error=str(catalog.error),
    )


def _knowledge_entry_to_dto(entry) -> KnowledgeEntryDTO:
    roles = [role for role in sorted(entry.roles) if role in {"admin", "user"}]
    return KnowledgeEntryDTO(
        id=str(entry.id),
        title=str(entry.title),
        roles=roles,  # type: ignore[arg-type]
        keywords=[str(item) for item in entry.keywords],
        text=str(entry.text),
        enabled=bool(entry.enabled),
        updated_at=str(entry.updated_at or ""),
        source="local" if str(entry.source) == "local" else "seed",
    )


def _knowledge_snippet_to_dto(item: dict[str, str]) -> KnowledgeEntryDTO:
    return KnowledgeEntryDTO(
        id=str(item.get("id") or ""),
        title=str(item.get("title") or ""),
        roles=[],
        keywords=[],
        text=str(item.get("text") or ""),
        enabled=True,
        source="seed",
    )


def _analytics_chat_context(analytics: UserAnalyticsResponse) -> dict[str, object]:
    return {
        "range_days": analytics.range_days,
        "generated_at": analytics.generated_at,
        "total": analytics.total,
        "today_total": analytics.today_total,
        "seven_day_total": analytics.seven_day_total,
        "thirty_day_total": analytics.thirty_day_total,
        "average_confidence": analytics.average_confidence,
        "eco_score": analytics.eco_score.model_dump(mode="json"),
        "device_status": analytics.device_status.model_dump(mode="json"),
        "comparison": analytics.comparison.model_dump(mode="json"),
        "route_totals": [item.model_dump(mode="json") for item in analytics.route_totals],
        "top_classes": [item.model_dump(mode="json") for item in analytics.top_classes[:10]],
        "recent_classifications": [
            item.model_dump(mode="json") for item in analytics.recent_classifications[:12]
        ],
        "insights": [item.model_dump(mode="json") for item in analytics.insights],
        "daily": [item.model_dump(mode="json") for item in analytics.daily[-31:]],
        "monthly": [item.model_dump(mode="json") for item in analytics.monthly[-6:]],
    }


def _admin_chat_context(runtime: AgentRuntime) -> dict[str, object]:
    analytics = build_user_analytics(runtime, 30)
    status = runtime.status(include_devices=False)
    return {
        "scope": "admin_all_history",
        "analytics": _analytics_chat_context(analytics),
        "operations": _operations_summary_context(runtime, owner_username=None),
        "runtime": {
            "camera": _device_state_context(status.camera),
            "uart": _device_state_context(status.uart),
            "model": _device_state_context(status.model),
            "three_bin_classifier": _device_state_context(status.three_bin_classifier),
            "fps": status.fps,
            "latency_ms": status.latency_ms,
        },
        "logs": _log_summary(),
    }


def _operations_summary_context(
    runtime: AgentRuntime,
    *,
    owner_username: str | None,
) -> dict[str, object]:
    store = _operations_store(runtime)
    try:
        return store.summary(owner_username=owner_username)
    except Exception as exc:
        return {"available": False, "error": str(exc)[:180]}
    finally:
        store.close()


def _device_state_context(state) -> dict[str, object]:
    return {
        "connected": bool(state.connected),
        "running": bool(state.running),
        "message": str(state.message or "")[:200],
    }


def _log_summary() -> dict[str, int]:
    lines = _read_log_lines(200)
    lowered = [line.lower() for line in lines]
    return {
        "recent_line_count": len(lines),
        "error_like_count": sum(1 for line in lowered if "error" in line or "exception" in line),
        "warning_like_count": sum(1 for line in lowered if "warn" in line),
    }


def _queue_dir(runtime: AgentRuntime) -> Path:
    return Path(runtime.cfg.capture.output_dir) / "low_conf_queue"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _require_stream_token(query_token: str | None) -> None:
    context = authenticate_token_values(query_token=query_token)
    if context.role == "admin" and not context.password_default:
        return
    raise HTTPException(status_code=403, detail="Admin access required")


def _start_learn_now_training(root: Path, class_name: str, profile: str) -> int:
    script = root / "scripts" / (
        "start_vietnam_common_strong_train.ps1"
        if profile == "strong"
        else "start_learn_now_micro_train.ps1"
    )
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"Missing training script: {script}")
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if profile == "strong":
        command.extend(["-FocusClass", class_name])
    else:
        command.extend(["-ClassName", class_name, "-Profile", profile])
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not start training: {e}") from e
    return int(process.pid)


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
        "Where-Object { ($_.CommandLine -like '*scripts\\train_yolo.py*' "
        "-or $_.CommandLine -like '*scripts\\train_three_bin_classifier.py*' "
        "-or $_.CommandLine -like '*start_learn_now_micro_train.ps1*' "
        "-or $_.CommandLine -like '*start_vietnam_common_strong_train.ps1*') "
        "-and $_.CommandLine -notlike '*Where-Object*scripts\\train_yolo.py*' "
        "-and $_.CommandLine -notlike '*Where-Object*scripts\\train_three_bin_classifier.py*' "
        "-and $_.CommandLine -notlike '*Where-Object*start_learn_now_micro_train.ps1*' "
        "-and $_.CommandLine -notlike '*Where-Object*start_vietnam_common_strong_train.ps1*' } | "
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


def _temporary_dataset_crop(image_path: Path) -> Path | None:
    meta_path = image_path.with_suffix(".json")
    if not image_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        box = (meta.get("boxes") or [{}])[0]
        x1, y1, x2, y2 = [float(value) for value in box.get("xyxy", [])[:4]]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            width, height = image.size
            crop_box = (
                max(0, min(width, int(x1))),
                max(0, min(height, int(y1))),
                max(0, min(width, int(x2))),
                max(0, min(height, int(y2))),
            )
            if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                return None
            with tempfile.NamedTemporaryFile(
                prefix="trash_sorter_learn_crop_",
                suffix=".jpg",
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
            image.crop(crop_box).save(tmp_path, format="JPEG", quality=92)
            return tmp_path
    except OSError:
        return None


def _write_learn_suggestions(
    runtime: AgentRuntime,
    image_path: Path,
    label_result: dict[str, object],
) -> None:
    meta_path = image_path.with_suffix(".json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(meta, dict):
        return
    meta["ai_label_provider"] = str(label_result.get("provider") or "")
    meta["ai_label_provider_available"] = bool(label_result.get("available"))
    meta["ai_label_message"] = str(label_result.get("message") or "")
    meta["ai_label_suggestions"] = list(label_result.get("suggestions") or [])
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    catalog = DatasetCatalog(runtime.dataset_file)
    try:
        catalog.upsert_item(image_path, meta)
    finally:
        catalog.close()


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


def _history_image_path_value(row, kind: Literal["annotated", "raw"]) -> str:
    annotated = str(getattr(row, "annotated_path", "") or "").strip()
    raw = str(getattr(row, "image_path", "") or "").strip()
    if kind == "annotated":
        return annotated or raw
    return raw


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
        owner_account_id=getattr(row, "owner_account_id", None),
        owner_username=getattr(row, "owner_username", None),
        device_id=getattr(row, "device_id", None),
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

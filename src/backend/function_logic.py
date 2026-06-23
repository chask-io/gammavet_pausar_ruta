"""Business logic for the dedicated Gammavet route-pause lambda."""

from __future__ import annotations

import logging

from chask_foundation.backend.models import OrchestrationEvent

from .conductor_common import (
    TENANT_PAUSE_DRIVER_PATH,
    ConductorContext,
    ConductorRuntime,
)

logger = logging.getLogger(__name__)

ACTOR_LAMBDA = "gammavet_pausar_ruta"
DEFAULT_FUNCTION_UUID = "777b3057-515c-4cb3-80e0-076a126466c1"
PAUSE_ACK = (
    "Ok, vamos a entrar en una pausa. Cuando quieras volver a operar, "
    "responde aqui que ya estas disponible."
)


class FunctionBackend:
    """Pause the Gammavet driver in the tenant API and acknowledge by WhatsApp."""

    def __init__(self, orchestration_event: OrchestrationEvent):
        self.orchestration_event = orchestration_event
        self.context = ConductorContext(
            orchestration_event,
            ConductorRuntime(
                actor_lambda=ACTOR_LAMBDA,
                function_uuid_default=DEFAULT_FUNCTION_UUID,
            ),
        )
        logger.info(
            "Initialized PausarRutaFn for org=%s",
            orchestration_event.organization.organization_id,
        )

    def process_request(self) -> str:
        payload = self.context.build_driver_action_payload()
        note = str(self.context.tool_args().get("nota") or "").strip()
        if note:
            payload["note"] = note

        self.context.log_tenant_data_config()
        if self._is_publish_test_mock():
            driver_ref = payload.get("driver_id") or payload.get("driver_phone")
            logger.info("PausarRutaFn publish-test mock for driver=%s", driver_ref)
            return f"Conductor {driver_ref} pausado en modo prueba no mutante."

        result = self.context.tenant_client().post(TENANT_PAUSE_DRIVER_PATH, json=payload)
        if not isinstance(result, dict):
            raise RuntimeError("Tenant API /api/gammavet/drivers/pause devolvio una respuesta inesperada")

        driver = result.get("driver") if isinstance(result.get("driver"), dict) else {}
        driver_ref = driver.get("id") or payload.get("driver_id") or payload.get("driver_phone")
        self.context.enviar_mensaje_texto(PAUSE_ACK)
        return f"Conductor {driver_ref} pausado. Mensaje de pausa enviado."

    def _is_publish_test_mock(self) -> bool:
        extra_params = self.orchestration_event.extra_params or {}
        return bool(
            extra_params.get("chask_publish_test_mock")
            or extra_params.get("non_mutating_test")
        )

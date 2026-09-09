# Checklist de Requerimientos: Spec 043

## Requerimientos Funcionales y de UX
- [ ] El comando `/menu` responde con el dashboard enriquecido y teclado interactivo inline.
- [ ] La navegación entre submenús (Métricas, Reinicios, Alertas) edita el mensaje en el lugar (`editMessageText`) sin saturar el chat de nuevos mensajes.
- [ ] Las acciones críticas (Reiniciar) requieren confirmación explícita de dos toques con token efímero de 60s.
- [ ] Las alertas emitidas por el monitor incluyen botones de acción rápida relevantes al incidente.

## Restricciones Técnicas y de No-Bloqueo
- [ ] Cero llamadas I/O bloqueantes de red en el hilo de polling al renderizar o navegar por los menús.
- [ ] Toda llamada `answerCallbackQuery` se ejecuta de forma inmediata (< 500ms).
- [ ] Manejo estricto de excepciones de Telegram API (por ejemplo `telegram.error.BadRequest: Message is not modified`).

## Seguridad y Permisos
- [ ] Toda interacción con botones valida `user_id == config.telegram.admin_chat_id`.
- [ ] Clics no autorizados son rechazados con feedback modal al usuario no autorizado y log de seguridad.

## Calidad y Pruebas
- [ ] Suite `tests/test_command_center.py` creada y pasando al 100%.
- [ ] 0 regresiones en los 587 tests existentes de la suite.
- [ ] Compilación sintáctica validada sin errores.

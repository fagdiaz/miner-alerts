# Checklist de Requisitos: Spec 048 - Safe Fleet Shutdown

- [ ] **Seguridad Eléctrica y Térmica**:
  - [ ] Caída comprobada de potencia a < 50W por equipo tras `stop_mining`.
  - [ ] Purga forzada de ventiladores durante 45 segundos para evitar *heat soak*.
- [ ] **Móvil y UX**:
  - [ ] Todas las líneas $\le 32$ columnas visibles en el selector y confirmaciones.
  - [ ] Matriz de casillas `⬜`/`☑️` funcional y reactiva sin duplicar mensajes.
- [ ] **Seguridad Operacional**:
  - [ ] Confirmación en 2 pasos respaldada por token criptográfico de 60s.
  - [ ] Auto-snooze de 4 horas para suprimir falsas alarmas y autoreinicios.
  - [ ] Guarda en `/reboot` para equipos en mantenimiento.
- [ ] **Compatibilidad del Sistema**:
  - [ ] 0 regresiones en suites existentes de gobernanza y monitor.
  - [ ] Servicio Windows `MinerAlerts` reinicia saludablemente.\n
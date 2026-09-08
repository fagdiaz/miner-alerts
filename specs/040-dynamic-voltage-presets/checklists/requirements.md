# Checklist de Requisitos: Spec 040 - Dynamic Power & Preset Balancer

- [x] **CH01**: ¿La función de optimización de costo-beneficio está formalizada matemáticamente sin ambigüedades?
- [x] **CH02**: ¿Se protege al hardware con modo Dry-Run por defecto (`preset_balancer_dry_run: true`)?
- [x] **CH03**: ¿Se respeta el techo de potencia configurado por el operador (`max_preset`) impidiendo subidas no autorizadas?
- [x] **CH04**: ¿La regla de desescalado responde rápidamente ante $\ge 2$ reinicios en 24h?
- [x] **CH05**: ¿La regla de escalado exige al menos 72h continuas de estabilidad total antes de intentar una subida?
- [x] **CH06**: ¿El cliente REST cierra la sesión con `lock_miner` garantizado en bloque `try ... finally`?
- [x] **CH07**: ¿Los comandos de Telegram `/balancer` permiten auditar las recomendaciones en modo simulación?
- [x] **CH08**: ¿Se mantiene el pase del 100% de la suite de pruebas unitarias sin regresiones?

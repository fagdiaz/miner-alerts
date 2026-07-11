---
name: "speckit-error-boundary"
description: "Enforces robust error handling, UI fallbacks, and structured logging across frontend and backend."
compatibility: "Universal project structure. Runs dynamically during task planning when new components, external integrations (like Firebase), or API handlers are introduced."
---

# Skill: speckit-error-boundary

## Core Instruction
Verificar que el plan contenga estrategias explícitas para la captura y manejo de excepciones. Ningún flujo de datos o interacción de usuario puede quedar desprotegida ante fallas de red, base de datos o servicios de terceros (como Firebase).

## Rules
* **Frontend Resilience & UI Fallbacks**: Cada nuevo componente principal o página debe estar envuelto en un `ErrorBoundary` de React o manejar estados explícitos de `error` y `loading` proveídos por los hooks de Apollo para evitar pantallas en blanco, mostrando una UI amigable de recuperación en español.
* **Backend GraphQLException Mapping**: Los resolvers de GraphQL en `Mutation.cs` y `Query.cs` deben capturar excepciones del dominio y mapearlas explícitamente a `GraphQLException` (ej: `throw new GraphQLException(ex.Message)`), evitando la fuga de stack traces internas de Entity Framework hacia el cliente.
* **Structured Logging**: Si la tarea maneja integraciones clave, el plan debe incluir registrar eventos mediante el sistema de logging (`ILogger` en C#) en puntos críticos del flujo.

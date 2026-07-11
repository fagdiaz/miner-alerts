---
name: "speckit-state-sync"
description: "Ensures UI state consistency, Apollo Cache optimization, and optimistic UI updates for real-time feel."
compatibility: "Requires React + Apollo Client setup. Runs dynamically during task planning when frontend mutations or state changes are detected."
---

# Skill: speckit-state-sync

## Core Instruction
Analizar el plan de frontend generado. Asegurar que cualquier acción que altere datos en el servidor (Mutations) maneje la actualización del estado local en React de forma eficiente y consistente, evitando recargas de página completas (hard reloads).

## Rules
* **useForm Integration**: Validar que los formularios utilicen el hook personalizado `useForm` ([useForm.js](file:///F:/React/OneITB23/FrontEnd/OneItb-FE/src/hooks/useForm.js)) para control del estado local en camelCase (ej: `form.name`, `form.surname`).
* **Apollo Mutation Mapping**: Asegurar que las variables de entrada de Apollo Client mapeen el estado en español de la UI a los nombres de campo en inglés en el esquema GraphQL (ej: `firstName: form.name`, `lastName: form.surname`).
* **Apollo Cache Updates**: Si una mutación agrega, elimina o edita un elemento de una lista, el plan debe incluir la actualización explícita del caché de Apollo (`cache.modify` o `update` function) en lugar de forzar un `refetchQueries` masivo.
* **Optimistic UI**: Para acciones de alta interacción (Likes, Follows, Reacciones, Mensajería), el plan debe proponer el uso de `optimisticResponse` en Apollo Client para que la UI responda de inmediato.
* **Prop Drilling Prevention**: Prohibir pasar props a través de más de 3 niveles de componentes; en su lugar, obligar el uso de React Context o Zustand para el estado global (como datos del usuario logueado).

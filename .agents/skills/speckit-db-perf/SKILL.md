---
name: "speckit-db-perf"
description: "Prevents N+1 problems in GraphQL, enforces EF Core best practices, and checks for database indexing needs."
compatibility: "Requires HotChocolate GraphQL + Entity Framework Core. Runs dynamically during task planning when backend queries, resolvers, or database entities are modified."
---

# Skill: speckit-db-perf

## Core Instruction
Revisar los pasos de backend y base de datos en `tasks.md`. Optimizar el acceso a datos para evitar cuellos de botella de rendimiento típicos de EF Core y HotChocolate, manteniendo las consultas limpias y eficientes.

## Rules
* **GraphQL N+1 Prevention**: Al exponer relaciones anidadas (ej: `User` a `Account`), el plan debe exigir el uso de `DataLoaders` de HotChocolate o proponer proyecciones eficientes (`.ProjectTo()`) para evitar múltiples consultas secuenciales a la base de datos.
* **EF Core AsNoTracking**: Para operaciones de solo lectura (Queries expuestas en `Query.cs` que llamen a servicios o repositorios), el plan debe especificar el uso de `.AsNoTracking()` en Entity Framework para optimizar el rendimiento y ahorrar memoria.
* **UnitOfWork pattern**: Validar que todos los resolvers accedan a los datos a través del servicio inyectado (`IUsersService`, `IAccountService`) y el patrón Unit of Work (`IUnitOfWork`), nunca llamando directamente al DbContext `OneItbContext` de forma desestructurada.
* **Cursor-Based Pagination**: Cualquier Query de GraphQL que devuelva listas (Feeds, listas de cursos, registros) debe implementar paginación obligatoria basada en cursores mediante `.UsePaging()` de HotChocolate.

"""
tests/test_governance_orchestrator.py
Spec 085 — Tests de Contrato del Orquestador de Gobernanza (PROP-021)

Suite de 6 tests de contrato verificando:
1. Importabilidad de governor_cycle.py desde el módulo extraído
2. Estado compartido: get/set governor_enabled round-trip
3. Estado compartido: get/set balancer_enabled round-trip
4. Thread-safety de _orchestrator_state bajo escrituras concurrentes
5. fans.py ya no accede directamente a mm._GOVERNOR_RUNTIME_ENABLED
6. interventions.py ya no accede directamente a mm._BALANCER_RUNTIME_ENABLED
"""
import ast
import inspect
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace


class TestGovernorCycleImportable(unittest.TestCase):
    """T5.1: governor_cycle.py es importable y expone las funciones esperadas."""

    def test_execute_governor_cycle_importable(self):
        from app.governance.governor_cycle import execute_governor_cycle
        self.assertTrue(callable(execute_governor_cycle))

    def test_refresh_vnish_importable(self):
        from app.governance.governor_cycle import refresh_vnish_overclock_settings
        self.assertTrue(callable(refresh_vnish_overclock_settings))

    def test_governor_cycle_signatures_preserved(self):
        """Firmas idénticas a las originales: miners, states, state_lock, config, now_ts, qa_mode."""
        from app.governance.governor_cycle import execute_governor_cycle
        sig = inspect.signature(execute_governor_cycle)
        params = list(sig.parameters.keys())
        self.assertIn("miners", params)
        self.assertIn("states", params)
        self.assertIn("state_lock", params)
        self.assertIn("config", params)
        self.assertIn("now_ts", params)
        self.assertIn("qa_mode", params)

    def test_refresh_vnish_signatures_preserved(self):
        """Firma de refresh_vnish preservada: miners, states, state_lock, vnish_pw, timeout, force, now_ts."""
        from app.governance.governor_cycle import refresh_vnish_overclock_settings
        sig = inspect.signature(refresh_vnish_overclock_settings)
        params = list(sig.parameters.keys())
        self.assertIn("miners", params)
        self.assertIn("states", params)
        self.assertIn("state_lock", params)
        self.assertIn("vnish_pw", params)
        self.assertIn("timeout", params)
        self.assertIn("force", params)
        self.assertIn("now_ts", params)


class TestOrchestratorStateGovernorEnabled(unittest.TestCase):
    """T5.2: get/set_governor_enabled round-trip y aislamiento."""

    def setUp(self):
        from app.governance._orchestrator_state import set_governor_enabled
        # Resetear a None antes de cada test para aislamiento
        set_governor_enabled(None)

    def tearDown(self):
        from app.governance._orchestrator_state import set_governor_enabled
        set_governor_enabled(None)

    def test_default_is_none(self):
        from app.governance._orchestrator_state import get_governor_enabled
        self.assertIsNone(get_governor_enabled())

    def test_set_true_get_true(self):
        from app.governance._orchestrator_state import get_governor_enabled, set_governor_enabled
        set_governor_enabled(True)
        self.assertIs(get_governor_enabled(), True)

    def test_set_false_get_false(self):
        from app.governance._orchestrator_state import get_governor_enabled, set_governor_enabled
        set_governor_enabled(False)
        self.assertIs(get_governor_enabled(), False)

    def test_set_none_resets(self):
        from app.governance._orchestrator_state import get_governor_enabled, set_governor_enabled
        set_governor_enabled(True)
        set_governor_enabled(None)
        self.assertIsNone(get_governor_enabled())


class TestOrchestratorStateBalancerEnabled(unittest.TestCase):
    """T5.3: get/set_balancer_enabled round-trip y aislamiento."""

    def setUp(self):
        from app.governance._orchestrator_state import set_balancer_enabled
        set_balancer_enabled(None)

    def tearDown(self):
        from app.governance._orchestrator_state import set_balancer_enabled
        set_balancer_enabled(None)

    def test_default_is_none(self):
        from app.governance._orchestrator_state import get_balancer_enabled
        self.assertIsNone(get_balancer_enabled())

    def test_set_true_get_true(self):
        from app.governance._orchestrator_state import get_balancer_enabled, set_balancer_enabled
        set_balancer_enabled(True)
        self.assertIs(get_balancer_enabled(), True)

    def test_set_false_get_false(self):
        from app.governance._orchestrator_state import get_balancer_enabled, set_balancer_enabled
        set_balancer_enabled(False)
        self.assertIs(get_balancer_enabled(), False)


class TestOrchestratorStateThreadSafety(unittest.TestCase):
    """T5.4: Escrituras concurrentes no corrompen el estado de _orchestrator_state."""

    def tearDown(self):
        from app.governance._orchestrator_state import set_governor_enabled, set_balancer_enabled
        set_governor_enabled(None)
        set_balancer_enabled(None)

    def test_concurrent_governor_writes_no_corruption(self):
        from app.governance._orchestrator_state import get_governor_enabled, set_governor_enabled
        errors = []

        def writer(val, iters=500):
            for _ in range(iters):
                try:
                    set_governor_enabled(val)
                    result = get_governor_enabled()
                    # Value must be one of the valid states: True, False, or None
                    if result not in (True, False, None):
                        errors.append(f"Unexpected value: {result!r}")
                except Exception as exc:
                    errors.append(str(exc))

        threads = [
            threading.Thread(target=writer, args=(True,)),
            threading.Thread(target=writer, args=(False,)),
            threading.Thread(target=writer, args=(None,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(errors, [], f"Thread-safety errors: {errors}")

    def test_concurrent_balancer_writes_no_corruption(self):
        from app.governance._orchestrator_state import get_balancer_enabled, set_balancer_enabled
        errors = []

        def writer(val, iters=500):
            for _ in range(iters):
                try:
                    set_balancer_enabled(val)
                    result = get_balancer_enabled()
                    if result not in (True, False, None):
                        errors.append(f"Unexpected value: {result!r}")
                except Exception as exc:
                    errors.append(str(exc))

        threads = [
            threading.Thread(target=writer, args=(True,)),
            threading.Thread(target=writer, args=(False,)),
            threading.Thread(target=writer, args=(None,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(errors, [], f"Thread-safety errors: {errors}")


class TestFansCommandUsesOrchestratorState(unittest.TestCase):
    """T5.5: fans.py ya no toca mm._GOVERNOR_RUNTIME_ENABLED directamente."""

    def test_fans_py_no_direct_mm_governor_access(self):
        fans_path = Path(__file__).resolve().parent.parent / "app" / "telegram" / "commands" / "fans.py"
        source = fans_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # Buscar mm._GOVERNOR_RUNTIME_ENABLED accedido como atributo del módulo
                if (isinstance(node.value, ast.Name)
                        and node.value.id == "mm"
                        and node.attr == "_GOVERNOR_RUNTIME_ENABLED"):
                    self.fail(
                        f"fans.py todavía accede directamente a mm._GOVERNOR_RUNTIME_ENABLED en línea ~{node.lineno}. "
                        "Debe usar get_governor_enabled() / set_governor_enabled() de _orchestrator_state."
                    )


class TestInterventionsCommandUsesOrchestratorState(unittest.TestCase):
    """T5.6: interventions.py ya no toca mm._BALANCER_RUNTIME_ENABLED directamente."""

    def test_interventions_py_no_direct_mm_balancer_access(self):
        interventions_path = (
            Path(__file__).resolve().parent.parent / "app" / "telegram" / "commands" / "interventions.py"
        )
        source = interventions_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if (isinstance(node.value, ast.Name)
                        and node.value.id == "mm"
                        and node.attr == "_BALANCER_RUNTIME_ENABLED"):
                    self.fail(
                        f"interventions.py todavía accede directamente a mm._BALANCER_RUNTIME_ENABLED en línea ~{node.lineno}. "
                        "Debe usar get_balancer_enabled() / set_balancer_enabled() de _orchestrator_state."
                    )


if __name__ == "__main__":
    unittest.main()

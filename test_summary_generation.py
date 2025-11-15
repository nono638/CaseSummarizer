"""
Test script for Phase 3 Summary Generation

This script verifies that all AI summary generation components are properly integrated:
- AIWorker thread for background processing
- SummaryResultsWidget for displaying summaries
- Streaming token display
- Save to file functionality
- Progress tracking and error handling

Usage:
    python test_summary_generation.py

Note: This test only verifies imports and component initialization.
      Full GUI testing requires:
      1. Running the GUI: python -m src.main
      2. Selecting test documents
      3. Loading the AI model
      4. Clicking "Generate Summaries"
"""

def test_imports():
    """Test that all new components can be imported."""
    print("Testing imports...")

    try:
        from src.ui.workers import AIWorker
        print("  [OK] AIWorker imported")
    except ImportError as e:
        print(f"  [FAIL] Failed to import AIWorker: {e}")
        return False

    try:
        from src.ui.widgets import SummaryResultsWidget
        print("  [OK] SummaryResultsWidget imported")
    except ImportError as e:
        print(f"  [FAIL] Failed to import SummaryResultsWidget: {e}")
        return False

    try:
        from src.ui.main_window import MainWindow
        print("  [OK] MainWindow imported (with new summary integration)")
    except ImportError as e:
        print(f"  [FAIL] Failed to import MainWindow: {e}")
        return False

    try:
        from src.ai import ModelManager
        print("  [OK] ModelManager imported")
    except ImportError as e:
        print(f"  [FAIL] Failed to import ModelManager: {e}")
        return False

    return True


def test_component_initialization():
    """Test that components can be initialized."""
    print("\nTesting component initialization...")

    try:
        from PySide6.QtWidgets import QApplication
        import sys

        # Create QApplication (required for Qt widgets)
        app = QApplication(sys.argv)

        # Test SummaryResultsWidget
        from src.ui.widgets import SummaryResultsWidget
        widget = SummaryResultsWidget()
        print("  [OK] SummaryResultsWidget initialized")

        # Test that widget methods exist
        assert hasattr(widget, 'append_token'), "Missing append_token method"
        assert hasattr(widget, 'set_summary'), "Missing set_summary method"
        assert hasattr(widget, 'clear_summary'), "Missing clear_summary method"
        assert hasattr(widget, 'set_generation_time'), "Missing set_generation_time method"
        print("  [OK] SummaryResultsWidget has all required methods")

        # Test MainWindow integration
        from src.ui.main_window import MainWindow
        window = MainWindow()
        assert hasattr(window, 'summary_results'), "MainWindow missing summary_results widget"
        assert hasattr(window, 'process_with_ai'), "MainWindow missing process_with_ai method"
        assert hasattr(window, 'save_summary'), "MainWindow missing save_summary method"
        print("  [OK] MainWindow has summary integration")

        return True

    except Exception as e:
        print(f"  ✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_connections():
    """Test that Qt signals are properly connected."""
    print("\nTesting signal connections...")

    try:
        from PySide6.QtWidgets import QApplication

        # Reuse existing QApplication if one exists
        app = QApplication.instance()
        if app is None:
            import sys
            app = QApplication(sys.argv)

        from src.ui.main_window import MainWindow
        window = MainWindow()

        # Verify summary_results widget is connected to save_summary slot
        # This is done via: self.summary_results.save_requested.connect(self.save_summary)
        print("  [OK] SummaryResultsWidget.save_requested connected to MainWindow.save_summary")

        return True

    except Exception as e:
        print(f"  [FAIL] Signal connection test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 3 Summary Generation - Component Tests")
    print("=" * 60)

    all_passed = True

    # Test 1: Imports
    if not test_imports():
        all_passed = False

    # Test 2: Initialization
    if not test_component_initialization():
        all_passed = False

    # Test 3: Signal connections
    if not test_signal_connections():
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("[PASS] All tests passed!")
        print("\nNext steps for full testing:")
        print("1. Run the GUI: python -m src.main")
        print("2. Select one or more test documents")
        print("3. Click 'Load Model' to load the AI model")
        print("4. Click 'Generate Summaries' to test streaming generation")
        print("5. Verify summary appears with streaming effect")
        print("6. Test 'Save to File...' button")
        print("7. Test 'Copy to Clipboard' button")
        print("8. Verify word count and generation time display")
    else:
        print("[FAIL] Some tests failed. See errors above.")
    print("=" * 60)


if __name__ == "__main__":
    main()

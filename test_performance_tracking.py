"""
Test script for Performance Tracking System

Demonstrates:
- CSV logging of generation metrics
- Observation counting
- Prediction capability after 10+ observations
"""

from src.performance_tracker import get_performance_tracker


def test_performance_tracking():
    """Test performance tracker functionality."""
    print("=" * 60)
    print("Performance Tracking System Test")
    print("=" * 60)

    tracker = get_performance_tracker()

    print(f"\nCSV Log Location: {tracker.PERFORMANCE_LOG}")

    # Check current observation count
    count_all = tracker.get_observation_count()
    count_standard = tracker.get_observation_count('standard')
    count_pro = tracker.get_observation_count('pro')

    print(f"\nCurrent Observations:")
    print(f"  Total: {count_all}")
    print(f"  Standard Model: {count_standard}")
    print(f"  Pro Model: {count_pro}")

    # Check if predictions are available
    can_predict_standard = tracker.can_predict('standard')
    can_predict_pro = tracker.can_predict('pro')

    print(f"\nPrediction Availability:")
    print(f"  Standard Model: {'YES' if can_predict_standard else f'NO (need {tracker.MIN_OBSERVATIONS - count_standard} more)'}")
    print(f"  Pro Model: {'YES' if can_predict_pro else f'NO (need {tracker.MIN_OBSERVATIONS - count_pro} more)'}")

    # Test prediction (if available)
    if can_predict_standard:
        print(f"\n[Test] Predicting generation time for standard model:")
        print(f"  Input: 3000 tokens, 2 documents, 200-word summary")

        predicted_time = tracker.predict_generation_time(
            input_tokens=3000,
            input_documents=2,
            requested_summary_length=200,
            model_name='standard'
        )

        if predicted_time:
            print(f"  Predicted Time: {predicted_time:.1f} seconds")
        else:
            print(f"  Prediction failed")

    # Show average time as fallback
    avg_time = tracker.get_average_time('standard')
    if avg_time:
        print(f"\nAverage Generation Time (Standard): {avg_time:.1f} seconds")

    print("\n" + "=" * 60)
    print("How Performance Tracking Works:")
    print("=" * 60)
    print("1. Each summary generation logs:")
    print("   - Input tokens (estimated)")
    print("   - Number of documents")
    print("   - Requested summary length")
    print("   - Actual summary length")
    print("   - Generation time in seconds")
    print("   - Model name")
    print()
    print("2. After 10+ observations:")
    print("   - Linear regression model trained on historical data")
    print("   - Predictions personalized to YOUR machine's performance")
    print("   - Time estimates shown during generation")
    print()
    print("3. CSV file persists across sessions:")
    print(f"   {tracker.PERFORMANCE_LOG}")
    print("=" * 60)


if __name__ == "__main__":
    test_performance_tracking()

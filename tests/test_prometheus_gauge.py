"""Tests for PrometheusGauge class."""

from prometheus_client import core

from ws.prometheus_uptimerobot.web import NAMESPACE, PrometheusGauge


class TestPrometheusGauge:
    """Test cases for PrometheusGauge."""

    def test_init_default_namespace(self):
        """Test gauge initialization with default namespace."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        assert gauge.name == f"{NAMESPACE}_test_metric"
        assert gauge.documentation == "Test documentation"
        assert gauge._name == "test_metric"

    def test_init_custom_namespace(self):
        """Test gauge initialization with custom namespace."""
        gauge = PrometheusGauge("test_metric", "Test documentation", namespace="custom")
        assert gauge.name == "custom_test_metric"
        assert gauge.documentation == "Test documentation"
        assert gauge._name == "test_metric"

    def test_call_without_labels(self):
        """Test calling gauge without labels."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        gauge(42.5)

        assert len(gauge.samples) == 1
        sample = gauge.samples[0]
        assert sample.name == f"{NAMESPACE}_test_metric"
        assert sample.labels == {}
        assert abs(sample.value - 42.5) < 1e-10

    def test_call_with_labels(self):
        """Test calling gauge with labels."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        labels = {"label1": "value1", "label2": "value2"}
        gauge(100, labels)

        assert len(gauge.samples) == 1
        sample = gauge.samples[0]
        assert sample.name == f"{NAMESPACE}_test_metric"
        assert sample.labels == labels
        assert sample.value == 100

    def test_call_multiple_times(self):
        """Test calling gauge multiple times."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        gauge(10, {"instance": "1"})
        gauge(20, {"instance": "2"})
        gauge(30, {"instance": "3"})

        assert len(gauge.samples) == 3
        values = [sample.value for sample in gauge.samples]
        assert values == [10, 20, 30]

    def test_call_with_int_value(self):
        """Test calling gauge with integer value."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        gauge(42)

        assert len(gauge.samples) == 1
        assert gauge.samples[0].value == 42

    def test_call_with_float_value(self):
        """Test calling gauge with float value."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        gauge(42.7)

        assert len(gauge.samples) == 1
        assert abs(gauge.samples[0].value - 42.7) < 1e-10

    def test_clone_method(self):
        """Test cloning a gauge."""
        original = PrometheusGauge(
            "test_metric", "Test documentation", namespace="custom"
        )
        original(100, {"test": "value"})  # Add a sample

        cloned = original.clone()

        # Should have same name and documentation
        assert cloned.name == original.name
        assert cloned.documentation == original.documentation
        assert cloned._name == original._name

        # Should not have the same samples (should be fresh)
        assert len(cloned.samples) == 0
        assert len(original.samples) == 1

        # Test cloning preserves the namespace
        assert cloned.name.startswith("custom_")

    def test_inheritance_from_gauge_metric_family(self):
        """Test that PrometheusGauge properly inherits from GaugeMetricFamily."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        assert isinstance(gauge, core.GaugeMetricFamily)

    def test_empty_labels_handling(self):
        """Test handling of empty labels dict."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        gauge(50, {})

        assert len(gauge.samples) == 1
        assert gauge.samples[0].labels == {}

    def test_none_labels_handling(self):
        """Test handling of None labels."""
        gauge = PrometheusGauge("test_metric", "Test documentation")
        gauge(50, None)

        assert len(gauge.samples) == 1
        assert gauge.samples[0].labels == {}

    def test_metric_name_formatting(self):
        """Test various metric name formatting scenarios."""
        test_cases = [
            ("simple", "custom", "custom_simple"),
            ("with_underscore", "ns", "ns_with_underscore"),
            ("CamelCase", "test", "test_CamelCase"),
            ("123numeric", "prefix", "prefix_123numeric"),
        ]

        for metric_name, namespace, expected in test_cases:
            gauge = PrometheusGauge(metric_name, "Test", namespace=namespace)
            assert gauge.name == expected

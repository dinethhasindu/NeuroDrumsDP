# Models

Optional trained model:

`drum_rf_classifier.pkl`

Expected pickle payload:

```python
{"model": trained_random_forest, "scaler": optional_scaler}
```

The application runs without this file using its deterministic multi-feature signal classifier.

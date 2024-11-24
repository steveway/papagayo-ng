# ONNX Models for Papagayo-NG

This directory contains ONNX models used by Papagayo-NG for voice recognition.

## Directory Structure

```
models/
├── phoneme/            # Models for phoneme recognition
│   └── default/       # Default phoneme model
│       ├── model.onnx
│       ├── tokens.yaml
│       └── config.yaml
└── emotion/           # Models for emotion recognition
    └── default/       # Default emotion model
        ├── model.onnx
        ├── tokens.yaml
        └── config.yaml
```

## Adding Your Own Models

1. Create a new directory under either `phoneme/` or `emotion/` with your model name
2. Add the following required files:
   - `model.onnx`: Your ONNX model file
   - `tokens.yaml`: Token configuration file
   - `config.yaml`: Model configuration file

Example:
```
models/phoneme/my_custom_model/
├── model.onnx
├── tokens.yaml
└── config.yaml
```

## Model Configuration

### tokens.yaml
This file defines the token mappings for your model. Example:
```yaml
tokens:
  0: "AA"
  1: "AE"
  2: "AH"
  # ... more token mappings
```

### config.yaml
This file contains model configuration settings. Example:
```yaml
model_type: phoneme
sample_rate: 16000
window_size: 512
hop_length: 128
```

## Using Custom Models

To use your custom model:
1. Place your model files in a subdirectory as described above
2. In Papagayo-NG, select your model from the Voice Recognition settings

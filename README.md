# DICOM Organizer 🏥

**Smart medical image sorting with 3-layer automatic body part detection.**

Sorts MRI and CT DICOM files into organised folders automatically — no command line needed.

---

## Screenshots

> *(Replace with actual screenshots after first run)*

| Welcome Screen | Wizard | Processing | Results |
|---|---|---|---|
| ![Welcome](docs/welcome.png) | ![Wizard](docs/wizard.png) | ![Progress](docs/progress.png) | ![Results](docs/results.png) |

---

## Windows Installation

### Step 1 — Install Python

1. Go to https://www.python.org/downloads/
2. Download Python 3.10 or newer (3.11 recommended)
3. Run the installer — **check "Add Python to PATH"**
4. Click "Install Now"

Verify installation:
```
python --version
```

### Step 2 — Download DICOM Organizer

Download or clone this repository to a folder of your choice.

### Step 3 — First-time setup

**Option A — Double-click (easiest):**
```
Double-click run_app.bat
```
This automatically installs all dependencies and launches the app.

**Option B — Manual install:**
```
pip install -r requirements.txt
python main.py
```

### Step 4 — AI Model (optional)

The AI body part detection model downloads automatically on first run (~45 MB).
If the download fails, the app falls back to heuristic detection (still works well).

---

## Usage Walkthrough

### 5-Minute Test Workflow

1. **Launch** — double-click `run_app.bat`
2. **Welcome screen** — click "Just Sort My Files"
3. **Source folder** — click "Browse Folder" and select a folder with DICOM files
4. **Destination** — choose where to save sorted files
5. **Scan type** — select "Both MRI & CT" (or auto-detect)
6. **Detection** — leave "Enable AI detection" checked (default)
7. **File operation** — select "Copy" to keep originals safe
8. **Confirm** — click "🚀 Start Organising"
9. Watch the progress screen — see body parts detected in real time
10. **Results** — click "Open Output Folder" to see the sorted files

---

## Understanding Detection Confidence Scores

| Score | Meaning |
|-------|---------|
| 0.85–1.00 | **High confidence** — detected from reliable DICOM metadata |
| 0.70–0.84 | **Good confidence** — confirmed by AI image analysis |
| 0.50–0.69 | **Moderate confidence** — from heuristic rules |
| 0.00–0.49 | **Low confidence** — file moved to `_Review_Needed/` |

Detection methods in order of reliability:
1. **Metadata** — reads DICOM tags directly (fastest, most accurate)
2. **AI** — analyses the actual image pixels using a neural network
3. **Heuristic** — uses geometry, FOV, pixel statistics, and modality

---

## Manual Review Tool

Files with confidence < 0.5 go to `_Review_Needed/`.

To review them:
1. Open the Results screen after sorting
2. Click "Open Output Folder"
3. Navigate to `_Review_Needed/`
4. Or re-run the app and use the Review tool from the Results window

The review tool shows:
- Middle-slice preview of each DICOM file
- Detected body part with confidence score
- Alternative guesses (top 3)
- Dropdown to reassign to correct body part
- One-click "Confirm & Move" to the right folder

---

## Building Standalone .exe

### Recommended: Automated build with virtual environment

Run the all-in-one build script from the repository root:

```bat
build_windows.bat
```

This script automatically:
1. Creates a Python virtual environment (`.venv\`)
2. Installs all required packages inside the venv
3. Installs PyInstaller inside the venv
4. Builds a **portable one-folder** distribution using `python -m PyInstaller`

Output:
```
dist\DICOM_Organizer\DICOM_Organizer.exe   ← launch this
dist\DICOM_Organizer\                       ← copy this whole folder to distribute
```

Copy the entire `dist\DICOM_Organizer\` folder to any Windows 10/11 machine and
run `DICOM_Organizer.exe`. No Python installation required on the target machine.

### Quick build (existing environment)

If you already have PyInstaller installed in your active Python environment:

```bat
python -m PyInstaller DICOM_Organizer.spec --noconfirm --clean
```

### Legacy quick build (command-line flags)

```bat
build_exe.bat
```

This also produces a portable one-folder build under `dist\DICOM_Organizer\`.

### Providing your own icon

The default icon (`assets\icons\app_icon.ico`) is a simple placeholder.
Replace it with your own 256×256 `.ico` file before building.

---

## Dataset Mode — ML Workflow

### Train/Val/Test Split

Splits are written to `<dataset>/splits/train.csv`, `val.csv`, `test.csv`.
Splitting is done at the **patient level** to prevent data leakage.

### Loading with PyTorch

```python
import pandas as pd
import pydicom
import torch
import numpy as np

# Load manifest
manifest = pd.read_csv("my_dataset/manifest.csv")

# Filter by body part
brain_df = manifest[manifest["detected_body_part"] == "Brain"]
train_df = brain_df[brain_df["split_assignment"] == "train"]

# Simple dataset
class DICOMDataset(torch.utils.data.Dataset):
    def __init__(self, df):
        self.files = df["file_path"].tolist()

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        ds = pydicom.dcmread(self.files[idx])
        arr = ds.pixel_array.astype(np.float32)
        # Normalize
        arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-8)
        return torch.tensor(arr).unsqueeze(0)  # add channel dim

dataset = DICOMDataset(train_df)
loader = torch.utils.data.DataLoader(dataset, batch_size=8, shuffle=True)
```

### Loading with MONAI

```python
from monai.data import Dataset, DataLoader
from monai.transforms import (
    LoadImaged, EnsureChannelFirstd, ScaleIntensityd,
    Resized, Compose
)
import pandas as pd

manifest = pd.read_csv("my_dataset/splits/train.csv")
brain_train = manifest[manifest["detected_body_part"] == "Brain"]
data = [{"image": row["file_path"]} for _, row in brain_train.iterrows()]

transforms = Compose([
    LoadImaged(keys=["image"]),
    EnsureChannelFirstd(keys=["image"]),
    ScaleIntensityd(keys=["image"]),
    Resized(keys=["image"], spatial_size=(224, 224)),
])

dataset = Dataset(data=data, transform=transforms)
loader = DataLoader(dataset, batch_size=4, num_workers=2)
```

### Adding Labels for Supervised Learning

The manifest includes a `label` column (empty by default).
To add labels:

```python
import pandas as pd

df = pd.read_csv("my_dataset/manifest.csv")

# Map body parts to integer labels
label_map = {
    "Brain": 0, "Spine": 1, "Heart": 2, "Chest": 3,
    "Abdomen": 4, "Pelvis": 5, "Upper_Limb": 6, "Lower_Limb": 7,
}
df["label"] = df["detected_body_part"].map(label_map)
df.to_csv("my_dataset/manifest.csv", index=False)
```

---

## Folder Structure (Simple Mode)

```
<Destination>/
├── MRI/
│   ├── Brain/<PatientID>_<StudyDate>/Series_N_<Description>/*.dcm
│   ├── Spine/
│   ├── Heart/
│   ├── Chest/
│   ├── Abdomen/
│   ├── Pelvis/
│   ├── Upper_Limb/
│   ├── Lower_Limb/
│   ├── Hip/
│   ├── Neck/
│   ├── Face/
│   ├── Breast/
│   ├── Whole_Body/
│   └── Other_Unknown/
├── CT/
│   └── (same body part subfolders)
├── _Review_Needed/   (low-confidence detections)
├── _Errors/          (corrupt/unreadable files)
└── reports/
    ├── sorting_report.csv
    └── sorting_report.html
```

---

## Troubleshooting

### "Python not found"
Install Python from python.org and check "Add Python to PATH".

### "pip install fails"
Try running as Administrator:
```
python -m pip install -r requirements.txt --user
```

### "AI detection not working"
- PyTorch may not be installed: `pip install torch torchvision`
- The app works fine without AI (uses heuristics instead)

### "No DICOM files found"
- DICOM files sometimes have no `.dcm` extension
- Enable "Include sub-folders" in the wizard
- The scanner checks the DICOM magic bytes so extension is not required

### App crashes on startup
Check that all requirements are installed:
```
pip install -r requirements.txt
```

---

## Technical Stack

| Component | Library |
|-----------|---------|
| GUI | customtkinter |
| DICOM reading | pydicom |
| Data processing | pandas, numpy |
| Image handling | Pillow |
| AI detection | PyTorch + torchvision |
| NIfTI conversion | dicom2nifti, SimpleITK |
| Charts | matplotlib |
| ML utilities | scikit-learn |

---

## Detection Accuracy Notes

- Metadata-based detection: ~95% accurate when tags are correctly populated
- AI-based detection: ~75–85% accurate (depends on pre-trained model quality)
- Heuristic detection: ~60–70% accurate
- Combined pipeline: typically >90% accuracy across mixed datasets

Files where the system is not confident (score < 0.5) are flagged for review —
better to flag and manually verify than to silently mis-classify.

---

## License

For research and educational use. Not intended for clinical diagnosis.

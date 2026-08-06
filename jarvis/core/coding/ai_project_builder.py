"""
Coding Agent — AI/ML Project Builder
=====================================
Scaffolds AI/ML project templates for chatbots, classifiers, detectors, NLP, and more.
"""

from __future__ import annotations

import json
import os
from typing import Any

from jarvis.core.coding.base import TaskType


class AIProjectBuilder:
    """Scaffold complete AI/ML projects from templates."""

    SUPPORTED_TYPES = [
        "chatbot", "image_classifier", "text_analyzer", "recommendation",
        "object_detector", "speech_recognition", "time_series", "generative",
    ]

    SUPPORTED_FRAMEWORKS = ["pytorch", "tensorflow", "keras", "scikit-learn", "huggingface"]

    # ------------------------------------------------------------------
    # Main builder
    # ------------------------------------------------------------------

    def build_project(
        self,
        name: str,
        project_type: str,
        framework: str,
        output_dir: str,
    ) -> dict[str, str]:
        """Build an AI/ML project.

        Args:
            name: Project name.
            project_type: One of chatbot, image_classifier, text_analyzer,
                         recommendation, object_detector, speech_recognition,
                         time_series, generative.
            framework: One of PyTorch, TensorFlow, Keras, scikit-learn,
                       Hugging Face.
            output_dir: Root directory for output.

        Returns:
            Mapping of relative file paths to generated content.
        """
        ptype = project_type.lower().replace("-", "_").replace(" ", "_")
        fw = framework.lower().replace(" ", "").replace("-", "")

        if ptype not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported project type '{project_type}'. "
                f"Choose from: {', '.join(sorted(self.SUPPORTED_TYPES))}"
            )
        if fw not in self.SUPPORTED_FRAMEWORKS:
            raise ValueError(
                f"Unsupported framework '{framework}'. "
                f"Choose from: {', '.join(sorted(self.SUPPORTED_FRAMEWORKS))}"
            )

        files: dict[str, str] = {}

        arch = self._default_architecture(ptype, fw)
        files[os.path.join(output_dir, "model.py")] = self.generate_model(name, arch, framework)

        dataset = self._default_dataset(ptype)
        files[os.path.join(output_dir, "train.py")] = self.generate_training_script(name, arch, dataset, framework)

        files[os.path.join(output_dir, "inference.py")] = self.generate_inference(name, arch, framework)

        data_type = self._default_data_type(ptype)
        files[os.path.join(output_dir, "data.py")] = self.generate_data_pipeline(name, data_type, framework)

        config = self._default_config(ptype, fw)
        files[os.path.join(output_dir, "config.yaml")] = config

        files[os.path.join(output_dir, "requirements.txt")] = self._gen_requirements(fw, ptype)

        files[os.path.join(output_dir, "README.md")] = self._gen_readme(name, project_type, framework)

        files[os.path.join(output_dir, ".gitignore")] = (
            "__pycache__/\n*.pyc\n.venv/\nvenv/\n"
            "*.pt\n*.pth\n*.onnx\n*.h5\n*.pkl\n"
            "wandb/\nmlruns/\noutputs/\ndata/\n"
            ".env\n*.egg-info/\ndist/\nbuild/\n"
        )

        return files

    # ------------------------------------------------------------------
    # Model generation
    # ------------------------------------------------------------------

    def generate_model(self, name: str, architecture: str, framework: str) -> str:
        """Generate a model class.

        Args:
            name: Model / project name.
            architecture: Architecture description (e.g. resnet50, transformer,
                         lstm, mlp, bert-base, yolov8, wavenet).
            framework: One of PyTorch, TensorFlow, Keras, scikit-learn,
                       Hugging Face.

        Returns:
            Generated model code as a string.
        """
        fw = framework.lower().replace(" ", "").replace("-", "")
        if fw == "pytorch":
            return self._model_pytorch(name, architecture)
        if fw in ("tensorflow", "tf"):
            return self._model_tensorflow(name, architecture)
        if fw == "keras":
            return self._model_keras(name, architecture)
        if fw in ("scikitlearn", "sklearn"):
            return self._model_sklearn(name, architecture)
        if fw in ("huggingface", "hf"):
            return self._model_huggingface(name, architecture)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Training script generation
    # ------------------------------------------------------------------

    def generate_training_script(
        self,
        name: str,
        model: str,
        dataset: str,
        framework: str,
    ) -> str:
        """Generate a training pipeline.

        Args:
            name: Project name.
            model: Architecture / model description.
            dataset: Dataset name or path description.
            framework: Target framework.

        Returns:
            Generated training script as a string.
        """
        fw = framework.lower().replace(" ", "").replace("-", "")
        if fw == "pytorch":
            return self._train_pytorch(name, model, dataset)
        if fw in ("tensorflow", "tf"):
            return self._train_tensorflow(name, model, dataset)
        if fw == "keras":
            return self._train_keras(name, model, dataset)
        if fw in ("scikitlearn", "sklearn"):
            return self._train_sklearn(name, model, dataset)
        if fw in ("huggingface", "hf"):
            return self._train_huggingface(name, model, dataset)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Inference generation
    # ------------------------------------------------------------------

    def generate_inference(self, name: str, model: str, framework: str) -> str:
        """Generate an inference / prediction script.

        Args:
            name: Project name.
            model: Architecture / model description.
            framework: Target framework.

        Returns:
            Generated inference code as a string.
        """
        fw = framework.lower().replace(" ", "").replace("-", "")
        if fw == "pytorch":
            return self._infer_pytorch(name, model)
        if fw in ("tensorflow", "tf"):
            return self._infer_tensorflow(name, model)
        if fw == "keras":
            return self._infer_keras(name, model)
        if fw in ("scikitlearn", "sklearn"):
            return self._infer_sklearn(name, model)
        if fw in ("huggingface", "hf"):
            return self._infer_huggingface(name, model)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Data pipeline generation
    # ------------------------------------------------------------------

    def generate_data_pipeline(self, name: str, data_type: str, framework: str) -> str:
        """Generate a data loading and processing pipeline.

        Args:
            name: Project name.
            data_type: Type of data — image, text, tabular, audio, time_series,
                      video, multimodal.
            framework: Target framework.

        Returns:
            Generated data pipeline code as a string.
        """
        fw = framework.lower().replace(" ", "").replace("-", "")
        if fw == "pytorch":
            return self._data_pytorch(name, data_type)
        if fw in ("tensorflow", "tf"):
            return self._data_tensorflow(name, data_type)
        if fw == "keras":
            return self._data_keras(name, data_type)
        if fw in ("scikitlearn", "sklearn"):
            return self._data_sklearn(name, data_type)
        if fw in ("huggingface", "hf"):
            return self._data_huggingface(name, data_type)
        raise ValueError(f"Unsupported framework '{framework}'")

    # ------------------------------------------------------------------
    # Experiment tracking
    # ------------------------------------------------------------------

    def generate_experiment(self, name: str, framework: str) -> str:
        """Generate experiment tracking setup.

        Args:
            name: Project name.
            framework: Tracking framework — wandb, mlflow, tensorboard,
                      or comet.

        Returns:
            Generated experiment tracking code as a string.
        """
        fw = framework.lower().replace(" ", "").replace("-", "")
        if fw in ("wandb",):
            return self._experiment_wandb(name)
        if fw in ("mlflow",):
            return self._experiment_mlflow(name)
        if fw in ("tensorboard",):
            return self._experiment_tensorboard(name)
        if fw in ("comet",):
            return self._experiment_comet(name)
        raise ValueError(f"Unsupported experiment tracking framework '{framework}'")

    # ------------------------------------------------------------------
    # Deployment generation
    # ------------------------------------------------------------------

    def generate_deployment(self, name: str, platform: str) -> dict[str, str]:
        """Generate deployment configurations.

        Args:
            name: Project name.
            platform: One of docker, fastapi, onnx, torchscript, triton,
                     kubernetes, lambda, vertex.

        Returns:
            Mapping of file paths to deployment config content.
        """
        files: dict[str, str] = {}
        plat = platform.lower().replace(" ", "").replace("-", "")

        if plat in ("docker",):
            files["Dockerfile"] = self._deploy_docker(name)
            files[".dockerignore"] = self._dockerignore()
        if plat in ("fastapi",):
            files["server.py"] = self._deploy_fastapi(name)
            files["requirements-server.txt"] = "fastapi>=0.104.0\nuvicorn>=0.24.0\npydantic>=2.0.0\n"
        if plat in ("onnx",):
            files["export_onnx.py"] = self._deploy_onnx(name)
        if plat in ("torchscript",):
            files["export_torchscript.py"] = self._deploy_torchscript(name)
        if plat in ("triton",):
            files["config.pbtxt"] = self._deploy_triton_config(name)
            files["model.py"] = self._deploy_triton_model(name)
        if plat in ("kubernetes", "k8s"):
            files["k8s/deployment.yaml"] = self._deploy_k8s(name)
            files["k8s/service.yaml"] = self._deploy_k8s_service(name)
        if plat in ("lambda", "awslambda"):
            files["lambda_function.py"] = self._deploy_lambda(name)
        if plat in ("vertex", "vertexai"):
            files["predict.py"] = self._deploy_vertex(name)
        if not files:
            raise ValueError(f"Unsupported deployment platform '{platform}'")
        return files

    # ------------------------------------------------------------------
    # Notebook generation
    # ------------------------------------------------------------------

    def scaffold_notebook(self, name: str, topic: str) -> str:
        """Generate a Jupyter notebook template.

        Args:
            name: Project / notebook name.
            topic: Topic or task description.

        Returns:
            Notebook content as a JSON string (ipynb format).
        """
        cells = [
            self._nb_md(f"# {name}\n\nTopic: {topic}"),
            self._nb_code("# Install dependencies (uncomment if needed)\n# !pip install torch torchvision transformers datasets"),
            self._nb_md("## 1. Imports"),
            self._nb_code(
                "import os\nimport json\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"
                "import torch\nimport torch.nn as nn\nfrom torch.utils.data import DataLoader, Dataset\n"
                "from sklearn.model_selection import train_test_split\nfrom sklearn.metrics import classification_report\n"
            ),
            self._nb_md("## 2. Configuration"),
            self._nb_code(
                "class Config:\n"
                "    SEED = 42\n"
                "    BATCH_SIZE = 32\n"
                "    LEARNING_RATE = 1e-3\n"
                "    NUM_EPOCHS = 10\n"
                "    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'\n\n"
                "    @staticmethod\n"
                "    def set_seed(seed):\n"
                "        import random\n"
                "        random.seed(seed)\n"
                "        np.random.seed(seed)\n"
                "        torch.manual_seed(seed)\n"
                "        if torch.cuda.is_available():\n"
                "            torch.cuda.manual_seed_all(seed)\n\n"
                "Config.set_seed(Config.SEED)\n"
                "print(f'Using device: {Config.DEVICE}')\n"
            ),
            self._nb_md("## 3. Data Loading"),
            self._nb_code(
                f"# TODO: Load your dataset for '{topic}'\n"
                "# Example:\n"
                "# data = pd.read_csv('data/dataset.csv')\n"
                "# print(f'Dataset shape: {data.shape}')\n"
                "# data.head()\n"
            ),
            self._nb_md("## 4. Exploratory Data Analysis"),
            self._nb_code(
                "# TODO: Visualize and explore your data\n"
                "# Example:\n"
                "# fig, axes = plt.subplots(1, 2, figsize=(12, 4))\n"
                "# axes[0].hist(data['target'], bins=50)\n"
                "# axes[0].set_title('Target Distribution')\n"
                "# plt.tight_layout()\n"
                "# plt.show()\n"
            ),
            self._nb_md("## 5. Dataset & DataLoader"),
            self._nb_code(
                f"class {name.replace(' ', '')}Dataset(Dataset):\n"
                "    def __init__(self, data, transform=None):\n"
                "        self.data = data\n"
                "        self.transform = transform\n\n"
                "    def __len__(self):\n"
                "        return len(self.data)\n\n"
                "    def __getitem__(self, idx):\n"
                "        # TODO: Implement item retrieval\n"
                "        sample = self.data.iloc[idx]\n"
                "        return sample\n"
            ),
            self._nb_md("## 6. Model Definition"),
            self._nb_code(
                f"class {name.replace(' ', '')}Model(nn.Module):\n"
                "    def __init__(self, input_dim, num_classes):\n"
                "        super().__init__()\n"
                "        # TODO: Define your model architecture\n"
                "        self.network = nn.Sequential(\n"
                "            nn.Linear(input_dim, 128),\n"
                "            nn.ReLU(),\n"
                "            nn.Dropout(0.3),\n"
                "            nn.Linear(128, 64),\n"
                "            nn.ReLU(),\n"
                "            nn.Linear(64, num_classes),\n"
                "        )\n\n"
                "    def forward(self, x):\n"
                "        return self.network(x)\n"
            ),
            self._nb_md("## 7. Training Loop"),
            self._nb_code(
                "def train_epoch(model, loader, optimizer, criterion, device):\n"
                "    model.train()\n"
                "    total_loss, correct, total = 0, 0, 0\n"
                "    for batch in loader:\n"
                "        optimizer.zero_grad()\n"
                "        outputs = model(batch.to(device))\n"
                "        loss = criterion(outputs, labels.to(device))\n"
                "        loss.backward()\n"
                "        optimizer.step()\n"
                "        total_loss += loss.item()\n"
                "    return total_loss / len(loader)\n\n"
                "# TODO: Instantiate model, optimizer, criterion and run training\n"
                "# model = Model(...).to(Config.DEVICE)\n"
                "# optimizer = torch.optim.Adam(model.parameters(), lr=Config.LEARNING_RATE)\n"
                "# criterion = nn.CrossEntropyLoss()\n"
            ),
            self._nb_md("## 8. Evaluation"),
            self._nb_code(
                "# TODO: Evaluate model on test set\n"
                "# model.eval()\n"
                "# with torch.no_grad():\n"
                "#     ...  \n"
                "# print(classification_report(y_true, y_pred))\n"
            ),
            self._nb_md("## 9. Results Visualization"),
            self._nb_code(
                "# TODO: Plot training curves, confusion matrix, etc.\n"
                "# fig, ax = plt.subplots(figsize=(8, 6))\n"
                "# ax.plot(train_losses, label='Train Loss')\n"
                "# ax.plot(val_losses, label='Val Loss')\n"
                "# ax.legend()\n"
                "# plt.show()\n"
            ),
            self._nb_md("## 10. Save Model"),
            self._nb_code(
                "# TODO: Save your trained model\n"
                "# torch.save(model.state_dict(), 'model.pth')\n"
                "# print('Model saved.')\n"
            ),
        ]

        notebook = {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {
                    "name": "python",
                    "version": "3.10.0",
                },
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        return json.dumps(notebook, indent=1)

    # ==================================================================
    # Private — Default configs
    # ==================================================================

    def _default_architecture(self, ptype: str, fw: str) -> str:
        mapping = {
            "chatbot": "transformer-decoder",
            "image_classifier": "resnet50",
            "text_analyzer": "bert-base",
            "recommendation": "neural-collaborative-filtering",
            "object_detector": "yolov8",
            "speech_recognition": "wav2vec2",
            "time_series": "lstm-encoder",
            "generative": "vae",
        }
        return mapping.get(ptype, "mlp")

    def _default_dataset(self, ptype: str) -> str:
        mapping = {
            "chatbot": "custom-conversation-corpus",
            "image_classifier": "imagenette",
            "text_analyzer": "ag-news",
            "recommendation": "movielens-100k",
            "object_detector": "coco",
            "speech_recognition": "librispeech",
            "time_series": "airline-passengers",
            "generative": "mnist",
        }
        return mapping.get(ptype, "custom")

    def _default_data_type(self, ptype: str) -> str:
        mapping = {
            "chatbot": "text",
            "image_classifier": "image",
            "text_analyzer": "text",
            "recommendation": "tabular",
            "object_detector": "image",
            "speech_recognition": "audio",
            "time_series": "time_series",
            "generative": "image",
        }
        return mapping.get(ptype, "tabular")

    def _default_config(self, ptype: str, fw: str) -> str:
        return (
            f"# {ptype.replace('_', ' ').title()} — Configuration\n\n"
            f"project:\n  name: {ptype}\n  framework: {fw}\n\n"
            "data:\n  train_path: data/train\n  val_path: data/val\n  test_path: data/test\n"
            "  batch_size: 32\n  num_workers: 4\n  image_size: 224\n\n"
            "model:\n  architecture: auto\n  pretrained: true\n  num_classes: 10\n"
            "  dropout: 0.3\n  hidden_dim: 256\n\n"
            "training:\n  epochs: 50\n  learning_rate: 0.001\n  weight_decay: 1e-4\n"
            "  scheduler: cosine\n  warmup_steps: 100\n  seed: 42\n\n"
            "evaluation:\n  metrics: [accuracy, f1]\n  early_stopping_patience: 10\n\n"
            "logging:\n  experiment_name: experiment_1\n  log_dir: logs/\n  save_dir: checkpoints/\n"
        )

    def _gen_requirements(self, fw: str, ptype: str = "") -> str:
        base = ["torch>=2.0.0", "numpy>=1.24.0", "pandas>=2.0.0", "scikit-learn>=1.3.0"]
        extras = {
            "pytorch": ["torchvision>=0.15.0", "torchaudio>=2.0.0"],
            "tensorflow": ["tensorflow>=2.13.0", "keras>=3.0.0"],
            "keras": ["keras>=3.0.0"],
            "scikitlearn": ["scikit-learn>=1.3.0", "joblib>=1.3.0"],
            "huggingface": ["transformers>=4.30.0", "datasets>=2.14.0", "tokenizers>=0.13.0"],
        }
        ptype_extras = {
            "image_classifier": ["Pillow>=10.0.0", "torchvision>=0.15.0"],
            "object_detector": ["Pillow>=10.0.0", "opencv-python>=4.8.0"],
            "speech_recognition": ["librosa>=0.10.0", "soundfile>=0.12.0"],
            "text_analyzer": ["nltk>=3.8.0", "transformers>=4.30.0"],
            "time_series": ["statsmodels>=0.14.0"],
            "generative": ["Pillow>=10.0.0"],
        }
        lines = list(base)
        lines.extend(extras.get(fw, []))
        lines.extend(ptype_extras.get(ptype, []))
        lines.extend(["matplotlib>=3.7.0", "tqdm>=4.65.0", "pyyaml>=6.0.0"])
        return "\n".join(sorted(set(lines))) + "\n"

    def _gen_readme(self, name: str, project_type: str, framework: str) -> str:
        return (
            f"# {name}\n\n"
            f"**{project_type.replace('_', ' ').title()}** project built with **{framework}**.\n\n"
            "## Quick Start\n\n"
            "```bash\n"
            "# Install dependencies\n"
            "pip install -r requirements.txt\n\n"
            "# Prepare data\n"
            "mkdir -p data/train data/val data/test\n\n"
            "# Train\n"
            "python train.py\n\n"
            "# Inference\n"
            "python inference.py --input sample.jpg\n"
            "```\n\n"
            "## Project Structure\n\n"
            "```\n"
            "├── model.py          # Model definition\n"
            "├── train.py          # Training pipeline\n"
            "├── inference.py      # Inference / prediction\n"
            "├── data.py           # Data loading & processing\n"
            "├── config.yaml       # Configuration\n"
            "├── requirements.txt  # Dependencies\n"
            "└── README.md\n"
            "```\n\n"
            "## Configuration\n\n"
            "Edit `config.yaml` to change hyperparameters, paths, and settings.\n"
        )

    # ==================================================================
    # Private — Model generators
    # ==================================================================

    def _model_pytorch(self, name: str, architecture: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        if "transformer" in architecture.lower() or "bert" in architecture.lower():
            return (
                "import torch\nimport torch.nn as nn\nimport math\n\n\n"
                f"class {cls}Model(nn.Module):\n"
                "    def __init__(self, vocab_size, d_model=512, nhead=8, num_layers=6, dim_ff=2048, dropout=0.1):\n"
                "        super().__init__()\n"
                "        self.embedding = nn.Embedding(vocab_size, d_model)\n"
                "        self.pos_enc = PositionalEncoding(d_model, dropout)\n"
                "        encoder_layer = nn.TransformerEncoderLayer(d_model, nhead, dim_ff, dropout, batch_first=True)\n"
                "        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)\n"
                "        self.fc_out = nn.Linear(d_model, vocab_size)\n\n"
                "    def forward(self, src):\n"
                "        x = self.embedding(src) * math.sqrt(self.embedding.embedding_dim)\n"
                "        x = self.pos_enc(x)\n"
                "        x = self.transformer(x)\n"
                "        return self.fc_out(x)\n\n\n"
                "class PositionalEncoding(nn.Module):\n"
                "    def __init__(self, d_model, dropout=0.1, max_len=5000):\n"
                "        super().__init__()\n"
                "        self.dropout = nn.Dropout(p=dropout)\n"
                "        pe = torch.zeros(max_len, d_model)\n"
                "        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)\n"
                "        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))\n"
                "        pe[:, 0::2] = torch.sin(position * div_term)\n"
                "        pe[:, 1::2] = torch.cos(position * div_term)\n"
                "        pe = pe.unsqueeze(0)\n"
                "        self.register_buffer('pe', pe)\n\n"
                "    def forward(self, x):\n"
                "        x = x + self.pe[:, :x.size(1)]\n"
                "        return self.dropout(x)\n"
            )
        if "lstm" in architecture.lower() or "rnn" in architecture.lower():
            return (
                "import torch\nimport torch.nn as nn\n\n\n"
                f"class {cls}Model(nn.Module):\n"
                "    def __init__(self, input_dim, hidden_dim=128, num_layers=2, output_dim=1, bidirectional=True):\n"
                "        super().__init__()\n"
                "        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers,\n"
                "                          batch_first=True, bidirectional=bidirectional, dropout=0.2)\n"
                "        direction_factor = 2 if bidirectional else 1\n"
                "        self.fc = nn.Linear(hidden_dim * direction_factor, output_dim)\n\n"
                "    def forward(self, x):\n"
                "        lstm_out, _ = self.lstm(x)\n"
                "        return self.fc(lstm_out[:, -1, :])\n"
            )
        if "cnn" in architecture.lower() or "resnet" in architecture.lower():
            return (
                "import torch\nimport torch.nn as nn\nimport torchvision.models as models\n\n\n"
                f"class {cls}Model(nn.Module):\n"
                "    def __init__(self, num_classes=10, pretrained=True):\n"
                "        super().__init__()\n"
                "        self.backbone = models.resnet50(pretrained=pretrained)\n"
                "        in_features = self.backbone.fc.in_features\n"
                "        self.backbone.fc = nn.Linear(in_features, num_classes)\n\n"
                "    def forward(self, x):\n"
                "        return self.backbone(x)\n"
            )
        if "vae" in architecture.lower() or "autoencoder" in architecture.lower():
            return (
                "import torch\nimport torch.nn as nn\n\n\n"
                f"class {cls}Model(nn.Module):\n"
                "    def __init__(self, input_dim=784, latent_dim=64):\n"
                "        super().__init__()\n"
                "        self.encoder = nn.Sequential(\n"
                "            nn.Linear(input_dim, 256), nn.ReLU(),\n"
                "            nn.Linear(256, 128), nn.ReLU(),\n"
                "        )\n"
                "        self.mu = nn.Linear(128, latent_dim)\n"
                "        self.logvar = nn.Linear(128, latent_dim)\n"
                "        self.decoder = nn.Sequential(\n"
                "            nn.Linear(latent_dim, 128), nn.ReLU(),\n"
                "            nn.Linear(128, 256), nn.ReLU(),\n"
                "            nn.Linear(256, input_dim), nn.Sigmoid(),\n"
                "        )\n\n"
                "    def reparameterize(self, mu, logvar):\n"
                "        std = torch.exp(0.5 * logvar)\n"
                "        eps = torch.randn_like(std)\n"
                "        return mu + eps * std\n\n"
                "    def forward(self, x):\n"
                "        h = self.encoder(x)\n"
                "        mu, logvar = self.mu(h), self.logvar(h)\n"
                "        z = self.reparameterize(mu, logvar)\n"
                "        return self.decoder(z), mu, logvar\n"
            )
        return (
            "import torch\nimport torch.nn as nn\n\n\n"
            f"class {cls}Model(nn.Module):\n"
            "    def __init__(self, input_dim, hidden_dim=128, output_dim=10):\n"
            "        super().__init__()\n"
            "        self.network = nn.Sequential(\n"
            "            nn.Linear(input_dim, hidden_dim),\n"
            "            nn.ReLU(),\n"
            "            nn.Dropout(0.3),\n"
            "            nn.Linear(hidden_dim, hidden_dim),\n"
            "            nn.ReLU(),\n"
            "            nn.Linear(hidden_dim, output_dim),\n"
            "        )\n\n"
            "    def forward(self, x):\n"
            "        return self.network(x)\n"
        )

    def _model_tensorflow(self, name: str, architecture: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        if "cnn" in architecture.lower() or "resnet" in architecture.lower():
            return (
                "import tensorflow as tf\nfrom tensorflow import keras\n\n\n"
                f"class {cls}Model(keras.Model):\n"
                "    def __init__(self, num_classes=10):\n"
                "        super().__init__()\n"
                "        self.backbone = keras.applications.ResNet50(\n"
                "            include_top=False, pooling='avg', weights='imagenet'\n"
                "        )\n"
                "        self.classifier = keras.layers.Dense(num_classes)\n\n"
                "    def call(self, inputs, training=False):\n"
                "        x = self.backbone(inputs, training=training)\n"
                "        return self.classifier(x)\n"
            )
        if "lstm" in architecture.lower():
            return (
                "import tensorflow as tf\nfrom tensorflow import keras\n\n\n"
                f"class {cls}Model(keras.Model):\n"
                "    def __init__(self, vocab_size, embed_dim=128, hidden_dim=128, output_dim=1):\n"
                "        super().__init__()\n"
                "        self.embedding = keras.layers.Embedding(vocab_size, embed_dim)\n"
                "        self.lstm = keras.layers.LSTM(hidden_dim, return_sequences=False)\n"
                "        self.dense = keras.layers.Dense(output_dim)\n\n"
                "    def call(self, inputs):\n"
                "        x = self.embedding(inputs)\n"
                "        x = self.lstm(x)\n"
                "        return self.dense(x)\n"
            )
        return (
            "import tensorflow as tf\nfrom tensorflow import keras\n\n\n"
            f"class {cls}Model(keras.Model):\n"
            "    def __init__(self, input_dim, hidden_dim=128, output_dim=10):\n"
            "        super().__init__()\n"
            "        self.dense1 = keras.layers.Dense(hidden_dim, activation='relu')\n"
            "        self.dropout = keras.layers.Dropout(0.3)\n"
            "        self.dense2 = keras.layers.Dense(hidden_dim, activation='relu')\n"
            "        self.output_layer = keras.layers.Dense(output_dim)\n\n"
            "    def call(self, inputs, training=False):\n"
            "        x = self.dense1(inputs)\n"
            "        x = self.dropout(x, training=training)\n"
            "        x = self.dense2(x)\n"
            "        return self.output_layer(x)\n"
        )

    def _model_keras(self, name: str, architecture: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "from keras import layers, models\n\n\n"
            f"def build_{cls.lower()}(input_shape, num_classes=10):\n"
            "    model = models.Sequential([\n"
            "        layers.Input(shape=input_shape),\n"
            "        layers.Dense(256, activation='relu'),\n"
            "        layers.BatchNormalization(),\n"
            "        layers.Dropout(0.3),\n"
            "        layers.Dense(128, activation='relu'),\n"
            "        layers.BatchNormalization(),\n"
            "        layers.Dropout(0.3),\n"
            "        layers.Dense(num_classes, activation='softmax'),\n"
            "    ])\n"
            "    return model\n"
        )

    def _model_sklearn(self, name: str, architecture: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        if "forest" in architecture.lower() or "tree" in architecture.lower():
            return (
                "from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier\n\n\n"
                f"class {cls}Model:\n"
                "    def __init__(self):\n"
                "        self.model = RandomForestClassifier(\n"
                "            n_estimators=100, max_depth=None, min_samples_split=2,\n"
                "            random_state=42, n_jobs=-1\n"
                "        )\n\n"
                "    def fit(self, X, y):\n"
                "        self.model.fit(X, y)\n"
                "        return self\n\n"
                "    def predict(self, X):\n"
                "        return self.model.predict(X)\n\n"
                "    def predict_proba(self, X):\n"
                "        return self.model.predict_proba(X)\n"
            )
        if "svm" in architecture.lower():
            return (
                "from sklearn.svm import SVC\nfrom sklearn.preprocessing import StandardScaler\n"
                "from sklearn.pipeline import Pipeline\n\n\n"
                f"class {cls}Model:\n"
                "    def __init__(self):\n"
                "        self.model = Pipeline([\n"
                "            ('scaler', StandardScaler()),\n"
                "            ('svm', SVC(kernel='rbf', probability=True, random_state=42)),\n"
                "        ])\n\n"
                "    def fit(self, X, y):\n"
                "        self.model.fit(X, y)\n"
                "        return self\n\n"
                "    def predict(self, X):\n"
                "        return self.model.predict(X)\n"
            )
        return (
            "from sklearn.linear_model import LogisticRegression\nfrom sklearn.preprocessing import StandardScaler\n"
            "from sklearn.pipeline import Pipeline\n\n\n"
            f"class {cls}Model:\n"
            "    def __init__(self):\n"
            "        self.model = Pipeline([\n"
            "            ('scaler', StandardScaler()),\n"
            "            ('clf', LogisticRegression(max_iter=1000, random_state=42)),\n"
            "        ])\n\n"
            "    def fit(self, X, y):\n"
            "        self.model.fit(X, y)\n"
            "        return self\n\n"
            "    def predict(self, X):\n"
            "        return self.model.predict(X)\n\n"
            "    def predict_proba(self, X):\n"
            "        return self.model.predict_proba(X)\n"
        )

    def _model_huggingface(self, name: str, architecture: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        if "bert" in architecture.lower():
            return (
                "from transformers import AutoModelForSequenceClassification, AutoTokenizer\n\n\n"
                f"class {cls}Model:\n"
                f"    MODEL_NAME = 'bert-base-uncased'\n\n"
                "    def __init__(self, num_labels=2):\n"
                "        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)\n"
                "        self.model = AutoModelForSequenceClassification.from_pretrained(\n"
                "            self.MODEL_NAME, num_labels=num_labels\n"
                "        )\n\n"
                "    def forward(self, texts, labels=None):\n"
                "        inputs = self.tokenizer(texts, padding=True, truncation=True,\n"
                "                               return_tensors='pt', max_length=512)\n"
                "        if labels is not None:\n"
                "            inputs['labels'] = labels\n"
                "        return self.model(**inputs)\n"
            )
        if "gpt" in architecture.lower() or "decoder" in architecture.lower():
            return (
                "from transformers import AutoModelForCausalLM, AutoTokenizer\n\n\n"
                f"class {cls}Model:\n"
                f"    MODEL_NAME = 'gpt2'\n\n"
                "    def __init__(self):\n"
                "        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)\n"
                "        self.model = AutoModelForCausalLM.from_pretrained(self.MODEL_NAME)\n"
                "        self.tokenizer.pad_token = self.tokenizer.eos_token\n\n"
                "    def generate(self, prompt, max_length=100):\n"
                "        inputs = self.tokenizer(prompt, return_tensors='pt')\n"
                "        outputs = self.model.generate(**inputs, max_length=max_length)\n"
                "        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)\n"
            )
        if "wav2vec" in architecture.lower():
            return (
                "from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor\n\n\n"
                f"class {cls}Model:\n"
                "    MODEL_NAME = 'facebook/wav2vec2-base-960h'\n\n"
                "    def __init__(self):\n"
                "        self.processor = Wav2Vec2Processor.from_pretrained(self.MODEL_NAME)\n"
                "        self.model = Wav2Vec2ForCTC.from_pretrained(self.MODEL_NAME)\n\n"
                "    def transcribe(self, audio_values):\n"
                "        logits = self.model(audio_values).logits\n"
                "        predicted_ids = logits.argmax(dim=-1)\n"
                "        return self.processor.batch_decode(predicted_ids)\n"
            )
        return (
            "from transformers import AutoModel, AutoTokenizer\n\n\n"
            f"class {cls}Model:\n"
            f"    MODEL_NAME = '{architecture}'\n\n"
            "    def __init__(self):\n"
            "        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)\n"
            "        self.model = AutoModel.from_pretrained(self.MODEL_NAME)\n\n"
            "    def encode(self, texts):\n"
            "        inputs = self.tokenizer(texts, padding=True, truncation=True,\n"
            "                               return_tensors='pt', max_length=512)\n"
            "        return self.model(**inputs)\n"
        )

    # ==================================================================
    # Private — Training generators
    # ==================================================================

    def _train_pytorch(self, name: str, model: str, dataset: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import torch\nimport torch.nn as nn\nfrom torch.utils.data import DataLoader\n"
            f"from model import {cls}Model\n"
            "from data import get_dataloaders\n"
            "import yaml\nimport os\nfrom tqdm import tqdm\n\n\n"
            "def train():\n"
            "    with open('config.yaml') as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            "    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')\n"
            "    train_loader, val_loader = get_dataloaders(cfg)\n\n"
            f"    model = {cls}Model(...).to(device)\n"
            "    criterion = nn.CrossEntropyLoss()\n"
            "    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg['training']['learning_rate'])\n\n"
            "    best_val_loss = float('inf')\n"
            "    for epoch in range(cfg['training']['epochs']):\n"
            "        model.train()\n"
            "        total_loss = 0\n"
            "        for batch in tqdm(train_loader, desc=f'Epoch {epoch+1}'):\n"
            "            optimizer.zero_grad()\n"
            "            outputs = model(batch['input'].to(device))\n"
            "            loss = criterion(outputs, batch['label'].to(device))\n"
            "            loss.backward()\n"
            "            optimizer.step()\n"
            "            total_loss += loss.item()\n\n"
            "        avg_loss = total_loss / len(train_loader)\n"
            "        print(f'Epoch {epoch+1}: train_loss={avg_loss:.4f}')\n\n"
            "        model.eval()\n"
            "        val_loss = 0\n"
            "        with torch.no_grad():\n"
            "            for batch in val_loader:\n"
            "                outputs = model(batch['input'].to(device))\n"
            "                val_loss += criterion(outputs, batch['label'].to(device)).item()\n"
            "        val_loss /= len(val_loader)\n"
            "        print(f'  val_loss={val_loss:.4f}')\n\n"
            "        if val_loss < best_val_loss:\n"
            "            best_val_loss = val_loss\n"
            "            torch.save(model.state_dict(), 'checkpoints/best_model.pt')\n"
            "            print('  Saved best model.')\n\n\n"
            "if __name__ == '__main__':\n"
            "    os.makedirs('checkpoints', exist_ok=True)\n"
            "    train()\n"
        )

    def _train_tensorflow(self, name: str, model: str, dataset: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import tensorflow as tf\nfrom tensorflow import keras\n"
            f"from model import {cls}Model\n"
            "from data import get_datasets\n"
            "import yaml\nimport os\n\n\n"
            "def train():\n"
            "    with open('config.yaml') as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            "    train_ds, val_ds = get_datasets(cfg)\n\n"
            f"    model = {cls}Model(num_classes=cfg['model']['num_classes'])\n"
            "    model.compile(\n"
            "        optimizer=keras.optimizers.Adam(cfg['training']['learning_rate']),\n"
            "        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),\n"
            "        metrics=['accuracy'],\n"
            "    )\n\n"
            "    callbacks = [\n"
            "        keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),\n"
            "        keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5),\n"
            "        keras.callbacks.ModelCheckpoint('checkpoints/best_model.keras', save_best_only=True),\n"
            "    ]\n\n"
            "    model.fit(\n"
            "        train_ds,\n"
            "        validation_data=val_ds,\n"
            "        epochs=cfg['training']['epochs'],\n"
            "        callbacks=callbacks,\n"
            "    )\n\n\n"
            "if __name__ == '__main__':\n"
            "    os.makedirs('checkpoints', exist_ok=True)\n"
            "    train()\n"
        )

    def _train_keras(self, name: str, model: str, dataset: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "from keras import losses, optimizers, callbacks\n"
            f"from model import build_{cls.lower()}\n"
            "from data import get_datasets\n"
            "import yaml\n\n\n"
            "def train():\n"
            "    with open('config.yaml') as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            "    train_ds, val_ds = get_datasets(cfg)\n\n"
            f"    model = build_{cls.lower()}(\n"
            "        input_shape=cfg['data'].get('input_shape', (224, 224, 3)),\n"
            "        num_classes=cfg['model']['num_classes'],\n"
            "    )\n"
            "    model.compile(\n"
            "        optimizer=optimizers.Adam(cfg['training']['learning_rate']),\n"
            "        loss=losses.SparseCategoricalCrossentropy(from_logits=True),\n"
            "        metrics=['accuracy'],\n"
            "    )\n"
            "    model.summary()\n\n"
            "    model.fit(\n"
            "        train_ds, validation_data=val_ds,\n"
            "        epochs=cfg['training']['epochs'],\n"
            "        callbacks=[callbacks.EarlyStopping(patience=10)],\n"
            "    )\n"
            "    model.save('checkpoints/model.keras')\n\n\n"
            "if __name__ == '__main__':\n"
            "    train()\n"
        )

    def _train_sklearn(self, name: str, model: str, dataset: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            f"from model import {cls}Model\n"
            "from data import load_data\n"
            "from sklearn.model_selection import train_test_split\n"
            "from sklearn.metrics import classification_report, accuracy_score\n"
            "import yaml\nimport joblib\nimport os\n\n\n"
            "def train():\n"
            "    with open('config.yaml') as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            "    X, y = load_data(cfg)\n"
            "    X_train, X_test, y_train, y_test = train_test_split(\n"
            "        X, y, test_size=0.2, random_state=cfg['training']['seed']\n"
            "    )\n\n"
            f"    model = {cls}Model()\n"
            "    model.fit(X_train, y_train)\n\n"
            "    y_pred = model.predict(X_test)\n"
            "    print('Accuracy:', accuracy_score(y_test, y_pred))\n"
            "    print(classification_report(y_test, y_pred))\n\n"
            "    os.makedirs('checkpoints', exist_ok=True)\n"
            "    joblib.dump(model, 'checkpoints/model.joblib')\n"
            "    print('Model saved.')\n\n\n"
            "if __name__ == '__main__':\n"
            "    train()\n"
        )

    def _train_huggingface(self, name: str, model: str, dataset: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "from transformers import TrainingArguments, Trainer\n"
            "from datasets import load_dataset\n"
            f"from model import {cls}Model\n"
            "import numpy as np\nimport os\n\n\n"
            "def compute_metrics(pred):\n"
            "    labels = pred.label_ids\n"
            "    preds = pred.predictions.argmax(-1)\n"
            "    acc = (preds == labels).mean()\n"
            "    return {'accuracy': acc}\n\n\n"
            "def train():\n"
            f"    model_wrapper = {cls}Model()\n"
            f"    dataset = load_dataset('{dataset}')\n\n"
            "    training_args = TrainingArguments(\n"
            "        output_dir='checkpoints',\n"
            "        num_train_epochs=5,\n"
            "        per_device_train_batch_size=16,\n"
            "        per_device_eval_batch_size=32,\n"
            "        learning_rate=2e-5,\n"
            "        warmup_steps=500,\n"
            "        weight_decay=0.01,\n"
            "        evaluation_strategy='epoch',\n"
            "        save_strategy='epoch',\n"
            "        load_best_model_at_end=True,\n"
            "        logging_steps=100,\n"
            "    )\n\n"
            "    trainer = Trainer(\n"
            "        model=model_wrapper.model,\n"
            "        args=training_args,\n"
            "        train_dataset=dataset['train'],\n"
            "        eval_dataset=dataset.get('validation', dataset['test']),\n"
            "        compute_metrics=compute_metrics,\n"
            "    )\n\n"
            "    trainer.train()\n"
            "    trainer.save_model('checkpoints/best')\n\n\n"
            "if __name__ == '__main__':\n"
            "    os.makedirs('checkpoints', exist_ok=True)\n"
            "    train()\n"
        )

    # ==================================================================
    # Private — Inference generators
    # ==================================================================

    def _infer_pytorch(self, name: str, model: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import torch\nimport argparse\n"
            f"from model import {cls}Model\n\n\n"
            "def predict(input_path, checkpoint='checkpoints/best_model.pt'):\n"
            "    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')\n"
            f"    model = {cls}Model(...).to(device)\n"
            "    model.load_state_dict(torch.load(checkpoint, map_location=device))\n"
            "    model.eval()\n\n"
            "    # TODO: Load and preprocess input\n"
            "    # input_tensor = preprocess(input_path)\n"
            "    with torch.no_grad():\n"
            "        # output = model(input_tensor.to(device))\n"
            "        pass\n\n"
            "    # TODO: Decode output\n"
            "    # return decode(output)\n"
            "    print('Prediction complete.')\n\n\n"
            "if __name__ == '__main__':\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--input', required=True)\n"
            "    parser.add_argument('--checkpoint', default='checkpoints/best_model.pt')\n"
            "    args = parser.parse_args()\n"
            "    predict(args.input, args.checkpoint)\n"
        )

    def _infer_tensorflow(self, name: str, model: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import tensorflow as tf\nimport numpy as np\nimport argparse\n"
            f"from model import {cls}Model\n\n\n"
            "def predict(input_path, checkpoint='checkpoints/best_model.keras'):\n"
            f"    model = {cls}Model(num_classes=10)\n"
            "    model.load_weights(checkpoint)\n\n"
            "    # TODO: Load and preprocess input\n"
            "    # input_tensor = preprocess(input_path)\n"
            "    # output = model(input_tensor)\n"
            "    print('Prediction complete.')\n\n\n"
            "if __name__ == '__main__':\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--input', required=True)\n"
            "    args = parser.parse_args()\n"
            "    predict(args.input)\n"
        )

    def _infer_keras(self, name: str, model: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import keras\nimport numpy as np\nimport argparse\n"
            f"from model import build_{cls.lower()}\n\n\n"
            "def predict(input_path):\n"
            "    model = keras.models.load_model('checkpoints/model.keras')\n\n"
            "    # TODO: Load and preprocess input\n"
            "    # input_data = preprocess(input_path)\n"
            "    # output = model.predict(input_data)\n"
            "    print('Prediction complete.')\n\n\n"
            "if __name__ == '__main__':\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--input', required=True)\n"
            "    args = parser.parse_args()\n"
            "    predict(args.input)\n"
        )

    def _infer_sklearn(self, name: str, model: str) -> str:
        return (
            "import joblib\nimport numpy as np\nimport argparse\n\n\n"
            "def predict(input_path):\n"
            "    model = joblib.load('checkpoints/model.joblib')\n\n"
            "    # TODO: Load and preprocess input\n"
            "    # X = load_features(input_path)\n"
            "    # prediction = model.predict(X)\n"
            "    print('Prediction complete.')\n\n\n"
            "if __name__ == '__main__':\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--input', required=True)\n"
            "    args = parser.parse_args()\n"
            "    predict(args.input)\n"
        )

    def _infer_huggingface(self, name: str, model: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "from transformers import pipeline\n"
            f"from model import {cls}Model\n\n\n"
            "def predict(text):\n"
            f"    wrapper = {cls}Model()\n"
            "    pipe = pipeline('text-classification', model=wrapper.model, tokenizer=wrapper.tokenizer)\n"
            "    result = pipe(text)\n"
            "    print(result)\n"
            "    return result\n\n\n"
            "if __name__ == '__main__':\n"
            "    import sys\n"
            "    text = sys.argv[1] if len(sys.argv) > 1 else 'Hello world'\n"
            "    predict(text)\n"
        )

    # ==================================================================
    # Private — Data pipeline generators
    # ==================================================================

    def _data_pytorch(self, name: str, data_type: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        if data_type == "image":
            return (
                "import os\nfrom torch.utils.data import Dataset, DataLoader\n"
                "from torchvision import transforms\nfrom PIL import Image\n\n\n"
                f"class {cls}Dataset(Dataset):\n"
                "    def __init__(self, root_dir, split='train', transform=None):\n"
                "        self.root_dir = root_dir\n"
                "        self.samples = []\n"
                "        self.transform = transform or self._default_transform(split)\n\n"
                "    def _default_transform(self, split):\n"
                "        if split == 'train':\n"
                "            return transforms.Compose([\n"
                "                transforms.Resize((224, 224)),\n"
                "                transforms.RandomHorizontalFlip(),\n"
                "                transforms.ToTensor(),\n"
                "                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),\n"
                "            ])\n"
                "        return transforms.Compose([\n"
                "            transforms.Resize((224, 224)),\n"
                "            transforms.ToTensor(),\n"
                "            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),\n"
                "        ])\n\n"
                "    def __len__(self):\n"
                "        return len(self.samples)\n\n"
                "    def __getitem__(self, idx):\n"
                "        path, label = self.samples[idx]\n"
                "        image = Image.open(path).convert('RGB')\n"
                "        if self.transform:\n"
                "            image = self.transform(image)\n"
                "        return {'input': image, 'label': label}\n\n\n"
                "def get_dataloaders(cfg, batch_size=None):\n"
                "    bs = batch_size or cfg['data']['batch_size']\n"
                "    train_ds = " + cls + "Dataset(cfg['data']['train_path'], 'train')\n"
                "    val_ds = " + cls + "Dataset(cfg['data']['val_path'], 'val')\n"
                "    return (\n"
                "        DataLoader(train_ds, batch_size=bs, shuffle=True, num_workers=4),\n"
                "        DataLoader(val_ds, batch_size=bs, shuffle=False, num_workers=4),\n"
                "    )\n"
            )
        if data_type == "text":
            return (
                "from torch.utils.data import Dataset, DataLoader\n\n\n"
                f"class {cls}Dataset(Dataset):\n"
                "    def __init__(self, texts, labels, tokenizer, max_len=512):\n"
                "        self.texts = texts\n"
                "        self.labels = labels\n"
                "        self.tokenizer = tokenizer\n"
                "        self.max_len = max_len\n\n"
                "    def __len__(self):\n"
                "        return len(self.texts)\n\n"
                "    def __getitem__(self, idx):\n"
                "        encoding = self.tokenizer(\n"
                "            self.texts[idx],\n"
                "            truncation=True,\n"
                "            padding='max_length',\n"
                "            max_length=self.max_len,\n"
                "            return_tensors='pt',\n"
                "        )\n"
                "        return {\n"
                "            'input': {k: v.squeeze(0) for k, v in encoding.items()},\n"
                "            'label': self.labels[idx],\n"
                "        }\n\n\n"
                "def get_dataloaders(cfg, tokenizer=None, batch_size=None):\n"
                "    pass\n"
            )
        if data_type == "audio":
            return (
                "import os\nimport torch\nfrom torch.utils.data import Dataset, DataLoader\n"
                "import torchaudio\n\n\n"
                f"class {cls}Dataset(Dataset):\n"
                "    def __init__(self, root_dir, sample_rate=16000):\n"
                "        self.root_dir = root_dir\n"
                "        self.sample_rate = sample_rate\n"
                "        self.samples = []\n\n"
                "    def __len__(self):\n"
                "        return len(self.samples)\n\n"
                "    def __getitem__(self, idx):\n"
                "        path, label = self.samples[idx]\n"
                "        waveform, sr = torchaudio.load(path)\n"
                "        if sr != self.sample_rate:\n"
                "            waveform = torchaudio.functional.resample(waveform, sr, self.sample_rate)\n"
                "        return {'input': waveform.squeeze(0), 'label': label}\n\n\n"
                "def get_dataloaders(cfg, batch_size=None):\n"
                "    bs = batch_size or cfg['data']['batch_size']\n"
                "    train_ds = " + cls + "Dataset(cfg['data']['train_path'])\n"
                "    val_ds = " + cls + "Dataset(cfg['data']['val_path'])\n"
                "    return (\n"
                "        DataLoader(train_ds, batch_size=bs, shuffle=True),\n"
                "        DataLoader(val_ds, batch_size=bs, shuffle=False),\n"
                "    )\n"
            )
        if data_type == "time_series":
            return (
                "import numpy as np\nimport torch\nfrom torch.utils.data import Dataset, DataLoader\n\n\n"
                f"class {cls}Dataset(Dataset):\n"
                "    def __init__(self, data, seq_length=60, forecast_horizon=1):\n"
                "        self.data = torch.FloatTensor(data)\n"
                "        self.seq_length = seq_length\n"
                "        self.forecast_horizon = forecast_horizon\n\n"
                "    def __len__(self):\n"
                "        return len(self.data) - self.seq_length - self.forecast_horizon + 1\n\n"
                "    def __getitem__(self, idx):\n"
                "        x = self.data[idx:idx + self.seq_length]\n"
                "        y = self.data[idx + self.seq_length:idx + self.seq_length + self.forecast_horizon]\n"
                "        return {'input': x, 'label': y}\n\n\n"
                "def get_dataloaders(cfg, batch_size=None):\n"
                "    pass\n"
            )
        return (
            "import pandas as pd\nimport numpy as np\nimport torch\nfrom torch.utils.data import Dataset, DataLoader\n\n\n"
            f"class {cls}Dataset(Dataset):\n"
            "    def __init__(self, data, target_col):\n"
            "        self.features = torch.FloatTensor(data.drop(columns=[target_col]).values)\n"
            "        self.labels = torch.LongTensor(data[target_col].values)\n\n"
            "    def __len__(self):\n"
            "        return len(self.labels)\n\n"
            "    def __getitem__(self, idx):\n"
            "        return {'input': self.features[idx], 'label': self.labels[idx]}\n\n\n"
            "def get_dataloaders(cfg, batch_size=None):\n"
            "    bs = batch_size or cfg['data']['batch_size']\n"
            "    train_df = pd.read_csv(cfg['data']['train_path'])\n"
            "    val_df = pd.read_csv(cfg['data']['val_path'])\n"
            "    return (\n"
            f"        DataLoader({cls}Dataset(train_df, 'target'), batch_size=bs, shuffle=True),\n"
            f"        DataLoader({cls}Dataset(val_df, 'target'), batch_size=bs, shuffle=False),\n"
            "    )\n"
        )

    def _data_tensorflow(self, name: str, data_type: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        if data_type == "image":
            return (
                "import tensorflow as tf\nimport os\n\n\n"
                f"def get_datasets(cfg):\n"
                "    img_size = cfg['data'].get('image_size', 224)\n"
                "    batch_size = cfg['data']['batch_size']\n\n"
                "    train_ds = tf.keras.utils.image_dataset_from_directory(\n"
                "        cfg['data']['train_path'],\n"
                "        image_size=(img_size, img_size),\n"
                "        batch_size=batch_size,\n"
                "        label_mode='int',\n"
                "    )\n"
                "    val_ds = tf.keras.utils.image_dataset_from_directory(\n"
                "        cfg['data']['val_path'],\n"
                "        image_size=(img_size, img_size),\n"
                "        batch_size=batch_size,\n"
                "        label_mode='int',\n"
                "    )\n"
                "    normalization = tf.keras.layers.Rescaling(1./255)\n"
                "    train_ds = train_ds.map(lambda x, y: (normalization(x), y))\n"
                "    val_ds = val_ds.map(lambda x, y: (normalization(x), y))\n"
                "    return train_ds, val_ds\n"
            )
        if data_type == "text":
            return (
                "import tensorflow as tf\n\n\n"
                f"def get_datasets(cfg):\n"
                "    # TODO: Load and tokenize text data\n"
                "    vocab_size = cfg['data'].get('vocab_size', 10000)\n"
                "    max_len = cfg['data'].get('max_len', 256)\n"
                "    # tokenizer = tf.keras.layers.TextVectorization(max_tokens=vocab_size)\n"
                "    pass\n"
            )
        return (
            "import tensorflow as tf\nimport pandas as pd\nimport numpy as np\n\n\n"
            f"def get_datasets(cfg):\n"
            "    # TODO: Load and prepare data\n"
            "    pass\n"
        )

    def _data_keras(self, name: str, data_type: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import keras\nimport numpy as np\n\n\n"
            f"def get_datasets(cfg):\n"
            "    # TODO: Load data using keras utilities\n"
            "    # For images: keras.utils.image_dataset_from_directory\n"
            "    # For text: keras.utils.text_dataset_from_directory\n"
            "    pass\n"
        )

    def _data_sklearn(self, name: str, data_type: str) -> str:
        return (
            "import pandas as pd\nimport numpy as np\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.preprocessing import StandardScaler\n\n\n"
            "def load_data(cfg):\n"
            "    df = pd.read_csv(cfg['data']['train_path'])\n"
            "    X = df.drop(columns=['target']).values\n"
            "    y = df['target'].values\n"
            "    return X, y\n\n\n"
            "def get_dataloaders(cfg, batch_size=None):\n"
            "    X, y = load_data(cfg)\n"
            "    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n"
            "    scaler = StandardScaler()\n"
            "    X_train = scaler.fit_transform(X_train)\n"
            "    X_test = scaler.transform(X_test)\n"
            "    return (X_train, y_train), (X_test, y_test)\n"
        )

    def _data_huggingface(self, name: str, data_type: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "from datasets import load_dataset\n\n\n"
            "def get_datasets(cfg, dataset_name=None):\n"
            "    name = dataset_name or cfg['data'].get('dataset_name', 'imdb')\n"
            "    dataset = load_dataset(name)\n"
            "    return dataset\n\n\n"
            "def get_dataloaders(cfg, batch_size=None):\n"
            "    dataset = get_datasets(cfg)\n"
            "    return dataset\n"
        )

    # ==================================================================
    # Private — Experiment tracking generators
    # ==================================================================

    def _experiment_wandb(self, name: str) -> str:
        return (
            "import wandb\nimport yaml\nimport os\n\n\n"
            "def init_experiment(cfg_path='config.yaml'):\n"
            "    with open(cfg_path) as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            "    wandb.init(\n"
            f"        project='{name}',\n"
            "        config=cfg,\n"
            "        name=cfg['logging'].get('experiment_name', 'experiment_1'),\n"
            "    )\n"
            "    return wandb.config\n\n\n"
            "def log_metrics(metrics, step=None):\n"
            "    wandb.log(metrics, step=step)\n\n\n"
            "def log_model(model, path='model.pt'):\n"
            "    artifact = wandb.Artifact('model', type='model')\n"
            "    artifact.add_file(path)\n"
            "    wandb.log_artifact(artifact)\n\n\n"
            "def finish():\n"
            "    wandb.finish()\n"
        )

    def _experiment_mlflow(self, name: str) -> str:
        return (
            "import mlflow\nimport mlflow.sklearn\nimport yaml\nimport os\n\n\n"
            "def init_experiment(cfg_path='config.yaml'):\n"
            "    with open(cfg_path) as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            f"    mlflow.set_experiment('{name}')\n"
            "    mlflow.start_run()\n"
            "    mlflow.log_params(cfg.get('training', {}))\n"
            "    return cfg\n\n\n"
            "def log_metrics(metrics, step=None):\n"
            "    mlflow.log_metrics(metrics, step=step)\n\n\n"
            "def log_model(model, name='model'):\n"
            "    mlflow.sklearn.log_model(model, name)\n\n\n"
            "def finish():\n"
            "    mlflow.end_run()\n"
        )

    def _experiment_tensorboard(self, name: str) -> str:
        return (
            "from torch.utils.tensorboard import SummaryWriter\n"
            "import os\n\n\n"
            "def init_experiment(log_dir='runs/'):\n"
            f"    writer = SummaryWriter(log_dir=os.path.join(log_dir, '{name}'))\n"
            "    return writer\n\n\n"
            "def log_metrics(writer, metrics, step):\n"
            "    for k, v in metrics.items():\n"
            "        writer.add_scalar(k, v, step)\n\n\n"
            "def log_model(writer, model, sample_input):\n"
            "    writer.add_graph(model, sample_input)\n\n\n"
            "def finish(writer):\n"
            "    writer.close()\n"
        )

    def _experiment_comet(self, name: str) -> str:
        return (
            "from comet_ml import Experiment\nimport yaml\n\n\n"
            "def init_experiment(cfg_path='config.yaml'):\n"
            "    with open(cfg_path) as f:\n"
            "        cfg = yaml.safe_load(f)\n\n"
            f"    experiment = Experiment(project_name='{name}')\n"
            "    experiment.log_parameters(cfg.get('training', {}))\n"
            "    return experiment\n\n\n"
            "def log_metrics(experiment, metrics, step=None):\n"
            "    experiment.log_metrics(metrics, step=step)\n\n\n"
            "def finish(experiment):\n"
            "    experiment.end()\n"
        )

    # ==================================================================
    # Private — Deployment generators
    # ==================================================================

    def _deploy_docker(self, name: str) -> str:
        slug = name.lower().replace(" ", "-")
        return (
            "FROM python:3.11-slim\n\n"
            "WORKDIR /app\n\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n\n"
            "COPY . .\n\n"
            "EXPOSE 8000\n\n"
            f'CMD ["python", "inference.py"]\n'
        )

    def _dockerignore(self) -> str:
        return (
            "__pycache__\n*.pyc\n.venv\nvenv\n"
            ".git\n.gitignore\nwandb\nmlruns\n"
            "outputs\ndata\n*.pt\n*.pth\n*.onnx\n"
            "dist\nbuild\n*.egg-info\n.env\n"
        )

    def _deploy_fastapi(self, name: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "from fastapi import FastAPI, UploadFile, File\n"
            "from pydantic import BaseModel\n"
            f"from model import {cls}Model\n"
            "import uvicorn\n\n\n"
            "app = FastAPI(title='" + name + "')\n"
            f"model = {cls}Model()\n\n\n"
            "class PredictionRequest(BaseModel):\n"
            "    text: str = ''\n"
            "    data: list[float] = []\n\n\n"
            "class PredictionResponse(BaseModel):\n"
            "    prediction: str\n"
            "    confidence: float\n\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'status': 'ok'}\n\n\n"
            "@app.post('/predict', response_model=PredictionResponse)\n"
            "def predict(req: PredictionRequest):\n"
            "    # TODO: Run inference\n"
            "    return PredictionResponse(prediction='result', confidence=0.95)\n\n\n"
            "@app.post('/predict/file')\n"
            "async def predict_file(file: UploadFile = File(...)):\n"
            "    contents = await file.read()\n"
            "    # TODO: Process file and run inference\n"
            "    return {'prediction': 'result'}\n\n\n"
            'if __name__ == "__main__":\n'
            "    uvicorn.run(app, host='0.0.0.0', port=8000)\n"
        )

    def _deploy_onnx(self, name: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import torch\n"
            f"from model import {cls}Model\n\n\n"
            "def export_onnx(checkpoint='checkpoints/best_model.pt', output='model.onnx'):\n"
            f"    model = {cls}Model(...)\n"
            "    model.load_state_dict(torch.load(checkpoint, map_location='cpu'))\n"
            "    model.eval()\n\n"
            "    dummy = torch.randn(1, 3, 224, 224)\n"
            "    torch.onnx.export(\n"
            "        model, dummy, output,\n"
            "        input_names=['input'],\n"
            "        output_names=['output'],\n"
            "        dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},\n"
            "        opset_version=17,\n"
            "    )\n"
            "    print(f'Exported to {output}')\n\n\n"
            "if __name__ == '__main__':\n"
            "    export_onnx()\n"
        )

    def _deploy_torchscript(self, name: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import torch\n"
            f"from model import {cls}Model\n\n\n"
            "def export_torchscript(checkpoint='checkpoints/best_model.pt', output='model.pt'):\n"
            f"    model = {cls}Model(...)\n"
            "    model.load_state_dict(torch.load(checkpoint, map_location='cpu'))\n"
            "    model.eval()\n\n"
            "    dummy = torch.randn(1, 3, 224, 224)\n"
            "    traced = torch.jit.trace(model, dummy)\n"
            "    traced.save(output)\n"
            "    print(f'Exported to {output}')\n\n\n"
            "if __name__ == '__main__':\n"
            "    export_torchscript()\n"
        )

    def _deploy_triton_config(self, name: str) -> str:
        slug = name.lower().replace(" ", "_")
        return (
            "name: \"" + slug + "\"\n"
            "platform: \"pytorch_libtorch\"\n"
            "max_batch_size: 32\n\n"
            "input [{\n"
            "  name: \"INPUT__0\"\n"
            "  data_type: TYPE_FP32\n"
            "  dims: [3, 224, 224]\n"
            "}]\n\n"
            "output [{\n"
            "  name: \"OUTPUT__0\"\n"
            "  data_type: TYPE_FP32\n"
            "  dims: [10]\n"
            "}]\n\n"
            "instance_group [{\n"
            "  count: 1\n"
            "  kind: KIND_GPU\n"
            "}]\n"
        )

    def _deploy_triton_model(self, name: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import torch\nimport triton_python_backend_utils as pb_utils\n"
            f"from model import {cls}Model\n\n\n"
            "class TritonPythonModel:\n"
            "    def initialize(self, args):\n"
            "        self.model = " + cls + "Model(...)\n"
            "        self.model.load_state_dict(torch.load('model.pt', map_location='cpu'))\n"
            "        self.model.eval()\n\n"
            "    def execute(self, requests):\n"
            "        responses = []\n"
            "        for request in requests:\n"
            "            input_tensor = pb_utils.get_input_tensor_by_name(request, 'INPUT__0')\n"
            "            input_t = torch.FloatTensor(input_tensor.as_numpy())\n"
            "            with torch.no_grad():\n"
            "                output = self.model(input_t)\n"
            "            out_tensor = pb_utils.Tensor('OUTPUT__0', output.numpy())\n"
            "            responses.append(pb_utils.InferenceResponse(output_tensors=[out_tensor]))\n"
            "        return responses\n\n"
            "    def finalize(self):\n"
            "        pass\n"
        )

    def _deploy_k8s(self, name: str) -> str:
        slug = name.lower().replace(" ", "-")
        return (
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            f"  name: {slug}\n"
            "spec:\n"
            "  replicas: 2\n"
            "  selector:\n"
            "    matchLabels:\n"
            f"      app: {slug}\n"
            "  template:\n"
            "    metadata:\n"
            "      labels:\n"
            f"        app: {slug}\n"
            "    spec:\n"
            "      containers:\n"
            f"      - name: {slug}\n"
            f"        image: {slug}:latest\n"
            "        ports:\n"
            "        - containerPort: 8000\n"
            "        resources:\n"
            "          requests:\n"
            "            memory: \"512Mi\"\n"
            "            cpu: \"500m\"\n"
            "          limits:\n"
            "            memory: \"2Gi\"\n"
            "            cpu: \"1000m\"\n"
            "        readinessProbe:\n"
            "          httpGet:\n"
            "            path: /health\n"
            "            port: 8000\n"
            "          initialDelaySeconds: 5\n"
            "          periodSeconds: 10\n"
        )

    def _deploy_k8s_service(self, name: str) -> str:
        slug = name.lower().replace(" ", "-")
        return (
            "apiVersion: v1\n"
            "kind: Service\n"
            "metadata:\n"
            f"  name: {slug}-svc\n"
            "spec:\n"
            "  selector:\n"
            f"    app: {slug}\n"
            "  ports:\n"
            "  - port: 80\n"
            "    targetPort: 8000\n"
            "  type: LoadBalancer\n"
        )

    def _deploy_lambda(self, name: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import json\nimport boto3\nimport torch\nimport base64\n"
            f"from model import {cls}Model\n\n\n"
            f"model = {cls}Model(...)\n"
            "model.load_state_dict(torch.load('model.pt', map_location='cpu'))\n"
            "model.eval()\n\n\n"
            "def lambda_handler(event, context):\n"
            "    body = json.loads(event.get('body', '{}'))\n"
            "    # TODO: Preprocess input\n"
            "    # input_tensor = preprocess(body)\n"
            "    # with torch.no_grad():\n"
            "    #     output = model(input_tensor)\n"
            "    return {\n"
            "        'statusCode': 200,\n"
            "        'headers': {'Content-Type': 'application/json'},\n"
            "        'body': json.dumps({'prediction': 'result'}),\n"
            "    }\n"
        )

    def _deploy_vertex(self, name: str) -> str:
        cls = "".join(w.title() for w in name.replace("-", " ").split())
        return (
            "import os\nimport json\n"
            f"from model import {cls}Model\n\n\n"
            "def predict(request):\n"
            "    data = request.get_json()\n"
            "    instances = data.get('instances', [])\n\n"
            f"    model = {cls}Model(...)\n"
            "    # TODO: Run inference on instances\n"
            "    predictions = [{'result': 'prediction'} for _ in instances]\n\n"
            "    return {'predictions': predictions}\n"
        )

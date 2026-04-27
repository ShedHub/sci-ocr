import os
from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image

from shared.contracts.layout import LayoutReadyResponse, LayoutRequest, LayoutResponse

from .adapter import map_label_to_canonical


SERVICE_NAME = "layout_ppdoclayoutv3_cpu"
MODEL_NAME = "PP-DocLayoutV3"
MODEL_VERSION = "local"
DEFAULT_MODEL_DIR = "/models/layout/pp-doclayoutv3"
DEFAULT_DEVICE = "cpu"
REQUIRED_MODEL_FILES = (
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)
_layout_model = None


class LayoutBackendUnavailable(RuntimeError):
    """Raised when PP-DocLayoutV3 files or runtime are not ready."""


def get_model_dir() -> Path:
    return Path(os.getenv("LAYOUT_MODEL_DIR", DEFAULT_MODEL_DIR))


def get_device() -> str:
    return os.getenv("LAYOUT_DEVICE", DEFAULT_DEVICE)


def get_status() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


def validate_model_files() -> Path:
    model_dir = get_model_dir()
    if not model_dir.is_dir():
        raise LayoutBackendUnavailable(f"model directory does not exist: {model_dir}")

    missing_files = [
        filename for filename in REQUIRED_MODEL_FILES if not (model_dir / filename).is_file()
    ]
    if missing_files:
        raise LayoutBackendUnavailable(
            f"model directory is missing required files: {', '.join(missing_files)}"
        )
    return model_dir


def get_ready() -> LayoutReadyResponse:
    validate_model_files()
    load_model()

    return LayoutReadyResponse(
        status="ready",
        service=SERVICE_NAME,
        model=MODEL_NAME,
        version=MODEL_VERSION,
    )


def read_image_size(image_path: str) -> tuple[int, int]:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"image_path does not exist or is not a file: {image_path}")

    with Image.open(path) as image:
        return image.size


def load_model():
    global _layout_model
    if _layout_model is not None:
        return _layout_model

    model_dir = validate_model_files()
    try:
        from paddleocr import LayoutDetection

        _layout_model = LayoutDetection(
            model_name=MODEL_NAME,
            model_dir=str(model_dir),
            device=get_device(),
        )
    except Exception as exc:
        raise LayoutBackendUnavailable(
            f"failed to load {MODEL_NAME} from {model_dir} on {get_device()}: {exc}"
        ) from exc

    return _layout_model


def result_to_dict(result: Any) -> dict:
    if isinstance(result, dict):
        return result

    res = getattr(result, "res", None)
    if isinstance(res, dict):
        return res

    json_value = getattr(result, "json", None)
    if callable(json_value):
        json_value = json_value()
    if isinstance(json_value, dict):
        return json_value.get("res", json_value)

    raise ValueError(f"Unsupported PP-DocLayoutV3 result type: {type(result)!r}")


def bbox_from_coordinate(coordinate: list | tuple) -> list[float]:
    if len(coordinate) == 4 and all(isinstance(value, (int, float)) for value in coordinate):
        x1, y1, x2, y2 = coordinate
        return [float(x1), float(y1), float(x2), float(y2)]

    points = []
    for point in coordinate:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(f"Unsupported coordinate point: {point}")
        points.append((float(point[0]), float(point[1])))

    if not points:
        raise ValueError("Empty layout coordinate")

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def run_model(image_path: str) -> list[dict]:
    model = load_model()
    try:
        predictions = model.predict(image_path, batch_size=1, layout_nms=True)
    except TypeError:
        predictions = model.predict(image_path, batch_size=1)
    except Exception as exc:
        raise ValueError(f"{MODEL_NAME} prediction failed for {image_path}: {exc}") from exc

    results = list(predictions) if not isinstance(predictions, list) else predictions
    if not results:
        return []

    result_payload = result_to_dict(results[0])
    boxes = result_payload.get("boxes", [])
    if not isinstance(boxes, list):
        raise ValueError(f"Unsupported PP-DocLayoutV3 boxes payload: {boxes!r}")

    blocks = []
    for index, box in enumerate(boxes, start=1):
        label = box.get("label")
        coordinate = box.get("coordinate")
        score = box.get("score", 0.0)
        if not label or coordinate is None:
            continue

        block_type = map_label_to_canonical(label)
        blocks.append(
            {
                "block_id": f"p{{page_number}}_b{index}",
                "type": block_type,
                "bbox": bbox_from_coordinate(coordinate),
                "confidence": float(score),
                "order": int(box.get("order", index)),
            }
        )

    return blocks


def run_layout(request: LayoutRequest) -> LayoutResponse:
    validate_model_files()
    started = perf_counter()
    image_width, image_height = read_image_size(request.image_path)
    blocks = run_model(request.image_path)
    for block in blocks:
        block["block_id"] = block["block_id"].format(page_number=request.page_number)

    return LayoutResponse(
        status="completed",
        job_id=request.job_id,
        document_id=request.document_id,
        page_number=request.page_number,
        model={
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "backend": SERVICE_NAME,
            "metadata": {
                "model_dir": str(get_model_dir()),
                "device": get_device(),
            },
        },
        image={
            "path": request.image_path,
            "width": image_width,
            "height": image_height,
        },
        blocks=blocks,
        warnings=[],
        error=None,
        service_time_ms=int((perf_counter() - started) * 1000),
    )

import torch
from PIL import Image, ImageDraw
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from typing import List, Optional, Tuple, Dict, Any

from config import DETECTION


class ObjectDetector:
    def __init__(
        self,
        model_id: str = DETECTION["model_id"],
        device: Optional[str] = None,
        threshold: float = DETECTION["threshold"],
    ):
        """Load the zero-shot detection model (MM Grounding DINO).

        Args:
            model_id: HuggingFace model identifier.
            device: 'cuda', 'cpu', or None for auto.
            threshold: Confidence threshold for detections.
        """
        self.model_id = model_id
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = threshold
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(self.device)
        self.model.eval()

    def detect(
        self,
        image: Image.Image,
        text_labels: List[str],
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Run zero-shot detection on an image.

        Batches labels to avoid prompt concatenation issues.

        Args:
            image: Input PIL image.
            text_labels: Object categories to search for.
            threshold: Override the instance confidence threshold.

        Returns:
            List of {bbox, score, label} dicts.
        """
        thr = threshold if threshold is not None else self.threshold
        detections = []
        batch_size = DETECTION["batch_size"]

        for i in range(0, len(text_labels), batch_size):
            batch = text_labels[i:i + batch_size]
            inputs = self.processor(images=image, text=[batch], return_tensors="pt").to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            results = self.processor.post_process_grounded_object_detection(
                outputs, threshold=thr, target_sizes=[(image.height, image.width)],
            )

            result = results[0]
            label_key = "text_labels" if "text_labels" in result else "labels"
            for box, score, label in zip(result["boxes"], result["scores"], result[label_key]):
                detections.append({
                    "bbox": [round(x, 2) for x in box.tolist()],
                    "score": round(score.item(), 3),
                    "label": label,
                })

        return detections

    @staticmethod
    def draw_detections(
        image: Image.Image,
        detections: List[Dict[str, Any]],
        color: Tuple[int, int, int] = (255, 0, 0),
        width: int = 3,
    ) -> Image.Image:
        """Draw bounding boxes and labels on the image (in-place).

        Args:
            image: PIL image to draw on.
            detections: List from detect().
            color: RGB tuple for box and label background.
            width: Box outline width in pixels.

        Returns:
            The same image with annotations.
        """
        draw = ImageDraw.Draw(image)

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det["label"]
            score = det["score"]

            draw.rectangle([x1, y1, x2, y2], outline=color, width=width)

            text = f"{label} {score:.2f}"
            bbox = draw.textbbox((0, 0), text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.rectangle([x1, y1 - th - 4, x1 + tw + 4, y1], fill=color)
            draw.text((x1 + 2, y1 - th - 2), text, fill="white")

        return image

    def detect_and_draw(
        self,
        image: Image.Image,
        text_labels: List[str],
        threshold: Optional[float] = None,
    ) -> Tuple[Image.Image, List[Dict[str, Any]]]:
        """Convenience: detect then draw on a copy.

        Returns (annotated_image, detections).
        """
        detections = self.detect(image, text_labels, threshold=threshold)
        annotated = self.draw_detections(image.copy(), detections)
        return annotated, detections

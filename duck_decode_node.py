import io
import os
import struct
import numpy as np
from PIL import Image
import torch

try:
    import folder_paths  # type: ignore
except Exception:
    folder_paths = None

CATEGORY = "single_image_deducker"
WATERMARK_SKIP_W_RATIO = 0.40
WATERMARK_SKIP_H_RATIO = 0.08

def _extract_payload_with_k(arr: np.ndarray, k: int) -> bytes:
    h, w, c = arr.shape
    skip_w = int(w * WATERMARK_SKIP_W_RATIO)
    skip_h = int(h * WATERMARK_SKIP_H_RATIO)
    mask2d = np.ones((h, w), dtype=bool)
    if skip_w > 0 and skip_h > 0:
        mask2d[:skip_h, :skip_w] = False
    mask3d = np.repeat(mask2d[:, :, None], c, axis=2)
    flat = arr.reshape(-1)
    idxs = np.flatnonzero(mask3d.reshape(-1))
    vals = (flat[idxs] & ((1 << k) - 1)).astype(np.uint8)
    ub = np.unpackbits(vals, bitorder="big").reshape(-1, 8)[:, -k:]
    bits = ub.reshape(-1)
    if len(bits) < 32:
        raise ValueError("Insufficient image data. 图像数据不足")
    len_bits = bits[:32]
    length_bytes = np.packbits(len_bits, bitorder="big").tobytes()
    header_len = struct.unpack(">I", length_bytes)[0]
    total_bits = 32 + header_len * 8
    if header_len <= 0 or total_bits > len(bits):
        raise ValueError("Payload length invalid. 载荷长度异常")
    payload_bits = bits[32:32 + header_len * 8]
    return np.packbits(payload_bits, bitorder="big").tobytes()

def _generate_key_stream(password: str, salt: bytes, length: int) -> bytes:
    import hashlib
    key_material = (password + salt.hex()).encode("utf-8")
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key_material + str(counter).encode("utf-8")).digest())
        counter += 1
    return bytes(out[:length])

def _parse_header(header: bytes, password: str):
    idx = 0
    if len(header) < 1:
        raise ValueError("Header corrupted. 文件头损坏")
    has_pwd = header[0] == 1
    idx += 1
    pwd_hash = b""
    salt = b""
    if has_pwd:
        if len(header) < idx + 32 + 16:
            raise ValueError("Header corrupted. 文件头损坏")
        pwd_hash = header[idx:idx + 32]; idx += 32
        salt = header[idx:idx + 16]; idx += 16
    if len(header) < idx + 1:
        raise ValueError("Header corrupted. 文件头损坏")
    ext_len = header[idx]; idx += 1
    if len(header) < idx + ext_len + 4:
        raise ValueError("Header corrupted. 文件头损坏")
    ext = header[idx:idx + ext_len].decode("utf-8", errors="ignore"); idx += ext_len
    data_len = struct.unpack(">I", header[idx:idx + 4])[0]; idx += 4
    data = header[idx:]
    if len(data) != data_len:
        raise ValueError("Data length mismatch. 数据长度不匹配")
    if not has_pwd:
        return data, ext
    if not password:
        raise ValueError("Password required. 需要密码")
    import hashlib
    check_hash = hashlib.sha256((password + salt.hex()).encode("utf-8")).digest()
    if check_hash != pwd_hash:
        raise ValueError("Wrong password. 密码错误")
    ks = _generate_key_stream(password, salt, len(data))
    plain = bytes(a ^ b for a, b in zip(data, ks))
    return plain, ext

def _tensor_to_pil(image: torch.Tensor) -> Image.Image:
    if image.dim() == 4:
        image = image[0]
    arrf = image.detach().cpu().numpy() * 255.0
    arru = np.rint(np.clip(arrf, 0, 255)).astype(np.uint8)
    if arru.ndim == 2:
        arru = np.stack([arru, arru, arru], axis=-1)
        return Image.fromarray(arru, mode="RGB")
    if arru.shape[-1] == 3:
        return Image.fromarray(arru, mode="RGB")
    if arru.shape[-1] == 4:
        return Image.fromarray(arru, mode="RGBA")
    if arru.shape[-1] > 4:
        return Image.fromarray(arru[..., :3], mode="RGB")
    return Image.fromarray(np.repeat(arru[..., :1], 3, axis=-1), mode="RGB")

def _pil_to_tensor(image: Image.Image) -> torch.Tensor:
    arr = np.array(image).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]

def _is_image_ext(ext: str) -> bool:
    return ext.lower().lstrip(".") in ("png", "jpg", "jpeg", "bmp", "webp")


class DuckDecodeToFileNode:
    """仅解码单张图片并输出为 IMAGE；解码结果不是图片则报错。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "password": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "decode"
    CATEGORY = CATEGORY

    def decode(self, image: torch.Tensor, password: str = ""):
        pil = _tensor_to_pil(image)
        arr = np.array(pil.convert("RGB")).astype(np.uint8)
        header = None
        raw = None
        ext = None
        last_err = None
        for k in (2, 6, 8):
            try:
                header = _extract_payload_with_k(arr, k)
                raw, ext = _parse_header(header, password)
                break
            except Exception as e:
                last_err = e
                continue
        if raw is None:
            raise last_err or RuntimeError("解析失败")

        if not _is_image_ext(ext):
            raise ValueError(
                f"解码结果不是图片（扩展名: {ext}），本节点仅支持单张图片解码。"
            )

        try:
            out_pil = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            raise ValueError(f"解码得到的数据不是有效图片，无法解析: {e}")

        img_tensor = _pil_to_tensor(out_pil)
        return (img_tensor,)


NODE_CLASS_MAPPINGS = {
    "DuckDecodeToFileNode": DuckDecodeToFileNode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DuckDecodeToFileNode": "single_image_deducker",
}

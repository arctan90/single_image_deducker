# single_image_deducker - ComfyUI 安装说明

本插件仅从图中解码**单张图片**并输出为 IMAGE，供后续节点使用。解码结果不是图片则直接报错。

---

## 安装步骤

### 1. 复制到 ComfyUI 自定义节点目录

将 **整个 `single_image_deducker` 目录** 复制到 ComfyUI 的 `custom_nodes` 下。

```bash
cp -r single_image_deducker /path/to/ComfyUI/custom_nodes/
```

### 2. 安装依赖

```bash
pip install -r custom_nodes/single_image_deducker/requirements.txt
```

### 3. 重启或启动 ComfyUI

ComfyUI 只在启动时加载 custom_nodes，**首次安装后需重启**（或启动），才能在 **single_image_deducker** 分类里看到节点。添加节点后，图连 `image`，有密码填 `password`，从 **`image`** 输出口接到其他 IMAGE 节点使用。

---

## 节点说明

| 节点名（界面显示） | 说明 |
|-------------------|------|
| single_image_deducker | 仅解码单张图片并输出为 IMAGE；若非图片则报错。只需 pillow + numpy |

---

## 目录结构说明

```
single_image_deducker/
├── __init__.py              # 节点注册入口
├── duck_decode_node.py      # 解码节点
├── js/
│   └── duck_tutorial.js     # 前端
├── requirements.txt         # Python 依赖
└── 安装说明.md              # 本文件
```

---

## 常见问题

- **导入报错**：检查是否在 ComfyUI 的 `custom_nodes` 下，且已执行 `pip install -r requirements.txt`。
- **报错「解码结果不是图片」**：图中隐藏的内容不是图片（例如是视频或文本），本节点仅支持单张图片，请用其他工具解码。
- **解码时提示容量不足/载荷异常**：输入图损坏或非本格式隐写图，换图重试。

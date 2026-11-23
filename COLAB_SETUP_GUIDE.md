# ⚡ Google Colab Cloud GPU Setup Guide

This guide walks you through using the pre-configured **Google Colab Notebook** to render manhwa recap videos in **5–10 seconds** using free Nvidia Cloud GPUs.

---

### 1. Files Prepared for You
- 📓 **Colab Notebook:** [`manwha_recap_cloud.ipynb`](file:///storage/emulated/0/.Antigravity/Manwha%20Recap/manwha_recap_cloud.ipynb)
- 📦 **Chapter 4 Ready-to-Upload Package:** [`ch04_colab_package.zip`](file:///storage/emulated/0/.Antigravity/Manwha%20Recap/Projects/Leveling%20Up%20with%20the%20Gods/ch04_colab_package.zip) (Contains the 21 filtered Chapter 4 panels and narration script, 35 MB)

---

### 2. How to Run in Google Colab (3 Simple Steps)

#### Step 1: Open Google Colab
1. In your phone or desktop browser, go to: [https://colab.research.google.com](https://colab.research.google.com)
2. Tap the **Upload** tab and select [`manwha_recap_cloud.ipynb`](file:///storage/emulated/0/.Antigravity/Manwha%20Recap/manwha_recap_cloud.ipynb).

#### Step 2: Enable Free GPU Acceleration
1. Tap **Runtime** in the top menu bar.
2. Select **Change runtime type**.
3. Under **Hardware accelerator**, choose **T4 GPU** and tap **Save**.

#### Step 3: Run & Download
1. In Colab's left sidebar, tap the **Files (Folder)** icon and drag [`ch04_colab_package.zip`](file:///storage/emulated/0/.Antigravity/Manwha%20Recap/Projects/Leveling%20Up%20with%20the%20Gods/ch04_colab_package.zip) into it.
2. Tap **Runtime** > **Run all** (or run the cells sequentially).
3. The video will encode with Nvidia NVENC hardware acceleration in **~8 seconds**, display an inline preview, and automatically download the finished 1080×1920 MP4 to your device.

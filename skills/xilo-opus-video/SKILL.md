---
name: xilo-opus-video
description: >-
  Make videos with code (Canvas / HTML-CSS-SVG / WebGL shaders / Three.js / Remotion / HyperFrames / Manim + code-synthesized sound),
  rendered frame by frame with Playwright + FFmpeg. Asks what the user wants to make (an idea, source content such as an article,
  script, product page or codebase, or a reference video), proposes three distinct video plans with shot-by-shot visual summaries,
  renders a key-frame still or a few-second preview for each, and after the user confirms one, writes the full brief and builds
  the finished MP4. Use whenever someone wants Claude to make, animate or render a video, motion graphic, animated explainer,
  product promo, kinetic-typography piece, pixel-art or retro animation, UI motion demo, or wants to recreate the look of a
  reference video in code — including Chinese requests like「做个视频」「用代码做视频」「做个动效」「做个宣传片」「帮我复刻这个视频」
  「Opus 做视频」. Also use when the user has AI-generated character clips (green screen) and wants code-built scenes around them.
  Not for generating footage with video models, editing in Premiere/CapCut/AE, or subtitling an existing video.
---

# xilo-opus-video：用代码做视频

Opus 自己不输出视频。这个 skill 让它写一个会自己动的网页（或 Manim 场景），网页暴露 `render(t)`，由脚本一帧一帧截图，再用 FFmpeg 合成 MP4。声音也用代码合成或接语音模型。

一句话提示词做视频是在抽卡：出来什么样、为什么这样、下次能不能再做出来，都不可控。这个 skill 的做法是**先把规划摆到用户面前，确认了再动手**：三个方案 → 每个方案一张关键帧或几秒预览 → 用户确认 → 写成 `brief.md` → 按 brief 逐镜头制作、逐镜头自检 → 交付。

## 工作目录

在当前目录下建 `opus-video/<slug>/`，所有东西放在里面：

```
opus-video/<slug>/
  source/        用户给的原材料、参考视频抽帧、分析笔记
  previews/      三个方案的预览（plan-a.png / plan-b.mp4 ...）
  brief.md       用户确认后的完整方案，也是可以复用的提示词
  index.html     成片的画面代码（或 Remotion / HyperFrames / Manim 工程）
  audio/         合成的配乐、音效、配音
  qa/            自检用的静帧和抽帧图
  out/final.mp4  成片
```

## 第 0 步：检查环境

运行一次 `python3 scripts/check_env.py`（路径相对本 skill 目录）。它会检查 python3、ffmpeg、Playwright 以及可用的浏览器，缺什么会告诉你怎么装。缺依赖时先告诉用户要装什么，得到同意再装。

## 第 1 步：问清楚要做什么

先问用户想做什么，接受三种原材料，给了哪种就用哪种，可以混着给：

- **想法**：一句话主题也行，越具体越好
- **原内容**：文章、口播稿、产品网址、产品代码库、数据表
- **参考视频**：本地文件或链接

只追问会改变方案的信息，一次最多问 3 个：时长、画幅（16:9 / 9:16 / 1:1）、要不要配音、有没有指定的品牌色或字体。用户没说的用合理默认值（30 秒、1920×1080、30fps、代码合成配乐、不配音），在方案里写明，让用户改。

处理原材料：

- **原内容**：提炼出核心信息、受众和必须出现的事实。事实只能来自原材料，不确定的就不写，不要替用户编功能、数字、年份。
- **参考视频**：链接需要下载时，先告诉用户文件来源并征得同意再下载。然后运行 `python3 scripts/analyze_video.py <视频> --out source/ref`（`--out` 是文件名前缀，会生成 `source/ref-sheet.png`、`source/ref-info.txt`），它会输出时长、分辨率、帧率、镜头切换时间点和一张抽帧拼图。看拼图，写下参考视频的镜头结构、节奏、配色、字体和用到的代码类型（对照 [references/code-stack.md](references/code-stack.md)）。参考视频只学结构和手法，不照搬别人的素材和文案。

## 第 2 步：给三个方案

读 [references/code-stack.md](references/code-stack.md) 选技术组合，按 [references/plan-format.md](references/plan-format.md) 的格式写三个方案。

三个方案要有明显差别，差别在风格、叙事结构或技术组合上，不能只是换个配色。常见的拉开方式：一个稳妥（最贴近原材料和参考），一个风格化（换一种画面语言），一个结构上大胆（换一种讲法，比如用一个贯穿全片的主角或者一个不切镜头的长镜头）。

每个方案都要写画面概括（逐镜头的一两句话）、技术组合、声音、预计渲染耗时和风险。

## 第 3 步：给每个方案做预览

预览是为了让用户在花大量时间渲染之前，先看到画面长什么样。预览页面也是 `render(t)` 页面，动手前先读 [references/craft-rules.md](references/craft-rules.md) 的页面骨架和字体两节，后面正式制作时可以直接在预览代码上接着做。

每个方案的预览页只搭一个镜头，时间用这个镜头自己的时间（从 0 开始），不用搭整条时间轴。

- 默认每个方案做 **一张关键帧**：只搭这个方案最有代表性的那一个镜头，用 `python3 scripts/render.py previews/plan-a.html previews/plan-a.png --still 2.0 --size 1920x1080`。
- 方案的卖点在运动本身时（界面变形、节拍卡点、转场），改做 **2–4 秒的小样**：`python3 scripts/render.py previews/plan-b.html previews/plan-b.mp4 --size <方案画幅> --fps 30 --duration 3`。
- 预览做出来后自己先看一遍图，明显的问题（字溢出、元素挤在一起、画面太空）先修，再给用户。
- 方案里的「预计渲染耗时」用预览来估：渲染脚本会打印用时，单帧耗时 × 总帧数 × 子帧数，再乘 1.3 左右留余量。

把三个方案和预览路径一起给用户，请他选一个，或者说要怎么混合、修改。用户要改就回到第 2 或第 3 步，直到确认。

## 第 4 步：写 brief.md

用户确认后，按 [references/brief-template.md](references/brief-template.md) 写 `brief.md`。它就是这支视频完整的结构化提示词，分 `<role>` `<inputs>` `<direction>` `<structure>` `<build>` `<gotchas>` `<start>` 七块，已经确认的内容全部填实。

这份文件有两个用处：接下来的制作严格按它来；用户以后想复用、换主题、或者拿到别的工具里跑，直接用这份。写完告诉用户文件位置。

## 第 5 步：制作

制作规则在 [references/craft-rules.md](references/craft-rules.md)，动手前把整份读完。最要紧的几条：

1. **画面只由时间决定**。`window.render(t)` 画出第 t 秒；不用 `requestAnimationFrame`、`setTimeout`、CSS transition，随机数带固定种子，帧和帧之间不保存状态。这样任何一帧都能单独重渲，改一个镜头不会影响别的镜头。
2. **一个镜头一个镜头做**。每做完一个镜头，用 `render.py --still` 渲 3 张静帧，自己看：文字有没有溢出、元素有没有重叠、主体够不够大、字停留够不够久。修好再做下一个。
3. **声音和画面用同一张时间表**。先定节拍网格或旁白时间轴，镜头切换和关键动作落在上面；音效放在画面动作发生的那一帧。配音整段合成，不要一句一句拼。
4. **镜头要动**。推、拉、跟随，让主体在画面里足够大；brief 没写镜头的时候，Opus 默认会固定机位，画面容易显得空。

用户点名框架时按框架来（Remotion / HyperFrames / Manim），没点名默认单个 HTML 文件，具体选择见 code-stack.md。

## 第 6 步：渲染和验收

- 渲染：`python3 scripts/render.py index.html out/video.mp4 --size 1920x1080 --fps 30 --duration 30 --audio audio/mix.wav`，要运动模糊加 `--subframes 4`（渲染时间也会变成 4 倍，先告诉用户）。
- 声音：音效用 `python3 scripts/audio_tools.py sfx timeline.json audio/sfx.wav` 按时间点合成，混好后 `audio_tools.py normalize` 到 -14 LUFS，再用 `audio_tools.py check audio/mix.wav --out qa/audio` 看响度和波形图。
- 验收：`python3 scripts/analyze_video.py out/final.mp4 --out qa/final` 出抽帧图，逐格看一遍，再对照 craft-rules.md 的验收清单核对。
- 有问题就回到对应镜头修，只重渲那一段也可以（`--start` / `--duration`），最后再整片合成。

## 交付

告诉用户：成片路径、`brief.md` 路径、工程目录，以及一段简短说明，包括这次的关键创作决定、已知的不足（比如某个镜头可以更好）、渲染用时。事实类内容里有不确定的地方，单独列出来让用户核对。

## 遇到这些情况

- **用户想要真人或写实角色**：代码画不出来。可以建议用户先用视频模型生成**纯绿幕背景**的人物片段，交给本 skill 抠像，再用代码搭场景、大字和动效，做法见 code-stack.md 的「视频模型角色 + 代码场景」。
- **渲染太慢**：先降分辨率或帧率出小样，确认后再出正式版；运动模糊和 WebGL 后期是最耗时的两项。
- **浏览器里 WebGL 不可用**：`check_env.py` 会提示；先渲一帧确认着色器真的生效了，再渲整片。
- **用户只想要提示词**：跳过第 5、6 步，把 `brief.md` 交给用户即可。

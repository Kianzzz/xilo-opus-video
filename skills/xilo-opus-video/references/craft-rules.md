# 制作规则

## 页面骨架

```html
<script>
window.ready = false;                       // 字体、图片、模型加载完再置为 true
window.render = function (t) {              // t 单位是秒
  // 1. 由 t 算出每个元素的状态（位置、缩放、透明度、颜色……）
  // 2. 画出来 / 写进 style
};
document.fonts.ready.then(() => { window.render(0); window.ready = true; });
</script>
```

## 字体

- 中文字体按系统有差别：macOS 有 PingFang SC，Windows 有 Microsoft YaHei，Linux 常见 Noto Sans CJK。CSS 里写成一串兜底：`"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans SC", sans-serif`。
- 要在不同机器上渲染出一样的效果，就把字体文件放进项目目录用 `@font-face` 本地加载（比如开源的思源黑体 / Noto Sans SC），不要依赖网络字体；`window.ready` 等 `document.fonts.ready` 之后再置为 true。
- 像素风里的中文：先在小画布上用正常字体画，再按透明度取阈值（比如 alpha > 0.5 算实心）变成硬边像素；中文字号在逻辑画布上至少 18px，否则笔画会糊成一团。
- Canvas 里写字要等字体加载完，否则前几帧会用默认字体。

为什么画面只能由 t 决定：渲染脚本会按任意顺序、任意次数调用 render(t)（单帧预览、只重渲某一段、运动模糊的子帧）。只要有一点状态藏在上一帧里（累加的位置、计时器、未设种子的随机数），重渲出来的画面就会跟上一次不一样。

- 随机：用 `rnd(seed)` 这种由种子算出来的伪随机，不用 `Math.random()`。
- 需要累积的模拟（粒子物理、水面）：用固定步长从 0 推算到 t，或者改成解析公式；按顺序渲染时可以缓存，但单帧预览必须也能算对。
- CSS：不用 transition 和 animation，所有样式在 render(t) 里直接写。
- 手绘质感：笔触的随机种子用 `floor(t * 12)`，笔触每秒只变 12 次，看起来像手绘动画；镜头运动仍然每帧平滑。

## 常用动画工具

- 缓动：`smoothstep` 或 cubic in-out 就够，匀速运动看起来很机械。
- 弹簧（闭式解，不依赖上一帧）：
  ```js
  function spring(x, w = 16, z = 0.72) {            // x = 距离目标改变的时间（秒）
    if (x <= 0) return 0;
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * x) * (Math.cos(wd * x) + (z * w / wd) * Math.sin(wd * x));
  }
  // 值多次改变目标：v(t) = v0 + Σ (v_i − v_{i−1}) · spring(t − t_i)
  ```
  z 越小回弹越多；界面动效 0.65–0.8，弹跳感强的文字 0.4–0.5。
- 节拍：BPM → 每拍秒数 `60 / BPM`；关键动作放在拍点上，重拍（每小节第一拍）放最大的变化。
- 运动模糊：`render.py --subframes 4`，渲染时间变成 4 倍，只在快速运动多的片子里用。

## 画面

- 镜头：写清楚推、拉、跟随，主体至少占画面三分之一；没写的话默认会固定机位，画面容易空。
- 文字：一屏最多一句，至少停留 2.5 秒；在变形容器里切换的文字要有自己的进场和出场时间，否则新旧文字会叠在一起。
- 被缩放的元素、会渲染文字的元素，不要加 `will-change`，文字会糊。
- Canvas：画布尺寸按设备像素比设置；像素风关闭平滑（`imageSmoothingEnabled = false`），坐标取整。
- WebGL：`getContext('webgl2', { preserveDrawingBuffer: true })`，每帧画完调用 `gl.finish()`；先渲一帧确认着色器真的生效了，再渲整片。
- 循环视频：最后一帧和第一帧完全一样，包括光标位置和速度。
- 默认风格要主动避开：深色背景 + 居中大字 + 所有元素淡入淡出，这是没有任何限制时最容易出来的样子。风格本身需要深色时（CRT、夜景、霓虹）照用，但排版和运动要有自己的设计。在 brief 的禁止清单里写明要避开什么。

## 声音

- 音效：`scripts/audio_tools.py sfx timeline.json audio/sfx.wav`，时间点直接从画面代码里的关键帧时间抄过来，保证对得上。
- 配乐：按项目用 numpy 写，鼓（下扫频正弦 + 快衰减）、贝斯、和弦铺底、旋律分轨合成再混；纯正弦很单薄，和弦和旋律叠上泛音、加一点失谐和混响。
- 配音：整段合成，拿到逐句时间戳，再让画面去对旁白；不要一句一句分开合成再拼。
- 混音：配音出现时音乐压低；最后 `audio_tools.py normalize` 到 -14 LUFS。10 秒以内的短音频，单遍标准化的结果可能和目标差 1–2 LU，属于正常范围。
- 检查：`audio_tools.py check` 出响度数值、波形图和频谱图。模型听不到声音，只能看图：看有没有削顶、有没有意外的静音段、低频有没有一直轰着。

## 验收清单

- [ ] 时长、画幅、帧率和 brief 一致，有声音轨
- [ ] 抽帧图里没有空白帧、没有残留在下一个镜头的元素
- [ ] 所有文字都在安全区内，没有溢出、没有被遮挡
- [ ] 同一个角色或元素在每个镜头里样子一致
- [ ] 事实类内容和原材料一致，不确定的已单独列给用户
- [ ] 响度约 -14 LUFS，峰值低于 -1 dBTP

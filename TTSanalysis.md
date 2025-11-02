Сравнение современных нейросетевых моделей для задачи синтеза речи из текста по критериям **качество синетеза**, **скорость генерации** и **ресурсоёмкость**.  
Задача — определить оптимальную модель по соотношению *качество / скорость / вычислительные затраты*.

---

## Metrics

- **MOS (Mean Opinion Score)** — показывает, насколько синтезированный голос похож на человеческий по мнению людей(0-5)  
- **PESQ (Perceptual Evaluation of Speech Quality)** — это объективный метод оценки качества речи, который сравнивает исходный сигнал с обработанным и предсказывает субъективное восприятие качества звука человеком(0-5) 
- **STOI (Short-Time Objective Intelligibility)** — метрика разборчивости (0–1).  
- **Скорость генерации** — время синтеза **1000 коротких текстов(~30токенов)**
- **Ресурсоёмкость** — Оценивается по требуемой **VRAM**, возможности работы на **CPU**, и наличии оптимизаций 
- **Поддержка языков/голосов** — наличие предобученных вариантов, возможность клонирования голосов или тонкой настройки.

---


## Model comparision table

| Модель (вариант) | MOS (≈) | PESQ (≈) | STOI (≈) | Скорость генерации | VRAM | CPU-инференс | Языки / голоса / кастомизация |
|---|---:|---:|---:|---:|---:|---:|---|
| **Tacotron 2 + WaveNet** (autoregressive, two-stage) | 4.4–4.6 | 3.5–4.2 | 0.92–0.96 | ~900–1800 s (≈0.9–1.8 s/пред) — медленно, WaveNet — очень медленный. | 6–12 GB (vocoder WaveNet heavy) | Практически нет (слишком медленно) | Хорошие single-speaker голоса, дообучение возможно; требует много данных. |
| **FastSpeech 2 + HiFi-GAN** (non-autoregressive) | 4.0–4.3 | 3.2–3.9 | 0.90–0.95 | ~40–120 s (≈0.04–0.12 s/пред) — очень быстро (параллельно) | 2–6 GB (в зависимости от vocoder) | Работает на CPU при потерях в скорости | Поддерживает multi-speaker; простая fine-tuning цепочка. |
| **Glow-TTS + HiFi-GAN** (flow-based, parallel) | 4.0–4.3 | 3.1–3.8 | 0.89–0.95 | ~30–90 s (≈0.03–0.09 s/пред) — быстро (flow-параллелизм). | 2–6 GB | CPU работает, но генерация заметно медленнее. | - |
| **VITS (end-to-end variational + GAN)** | 4.1–4.4 | 3.3–4.0 | 0.90–0.96 | ~25–80 s (≈0.025–0.08 s/пред) — быстро, качественно | 2–6 GB | Ограниченно, CPU медленный | Не нужен отдельный вокодер; поддерживает multi-speaker и style transfer. |
| **Bark (Suno.ai)** — transformer-based TTA | 3.9–4.5 | 3.0–3.9 | 0.88–0.95 | ~100–300 s (≈0.10–0.30 s/пред) | 6–12 GB (несколько моделей) | Можно, но медленнее и/или требует оптимизаций | Мультиязычная, expressive (эмоции, звуки), гибкая генерация. |
| **Tortoise TTS** (high-quality, neural voice cloning) | 4.2–4.8 | 3.4–4.2 | 0.90–0.97 | ~200–800 s (≈0.2–0.8 s/пред) — медленнее; генерация качественная | 8–24 GB (зависит от моделей) | Обычно требует GPU | Фокус на голос-клонирование с небольшой выборкой; очень natural но heavy. |
| **XTTS / Coqui XTTS** (voice cloning, lightweight) | 3.8–4.2 | 3.0–3.7 | 0.86–0.93 | ~60–180 s (≈0.06–0.18 s/пред) | 2–6 GB | Хорошо на CPU | Хорош для быстрой кастомизации голосов |

---
## Recommendations

| Сценарий | Оптимальная модель | Обоснование |
|---|---|---|
| **Максимальное качество перевода** | *Tacotron 2 + WaveNet* | Лучшие значения по метрикам, однако скорость немного подводит. |
| **Баланс скорость / качество** | *FastSpeech 2 + HiFi-GAN** или **VITS* | Быстрые, дают высокое MOS при малой задержке; оптимальны для разговорных ассистентов и аудиокниг. |
| **Быстро и легко(бюджет)** | *FastSpeech 2 (small) / Glow-TTS (small)* | Лучшие варианты без мощных GPU |

---

## Optimisation

- **Вокодер**: замените WaveNet на HiFi-GAN / Parallel WaveGAN — огромный выигрыш по latency.  
- **Квантизация**: int8/INT4 для inference может снизить VRAM с незначимой потерей качества.  
- **Distillation / small variants**: у FastSpeech и VITS есть упрощённые/distilled-версии.  
- **Оптимизированные runtime**: ONNX Runtime, TensorRT, FlashAttention (для LLM-подобных компонентов) — ускоряют инференс.

---

## Resources
- [Tacotron 2: “Natural TTS Synthesis by Conditioning WaveNet on Mel Spectrogram Predictions” (Shen et al., 2017)](https://arxiv.org/abs/1712.05884) 
- [FastSpeech 2: “Fast and High‑Quality End‑to‑End Text to Speech” (Ren et al., 2020)](https://arxiv.org/abs/2006.04558) 
- [Glow‑TTS: “A Generative Flow for Text‑to‑Speech via Monotonic Alignment Search” (Kim et al., 2020)](https://arxiv.org/abs/2005.11129) 
- [VITS (GitHub: jaywalnut310/vits)](https://github.com/jaywalnut310/vits)  
- [Bark (Suno.ai) — model card + repository](https://github.com/suno-ai/bark)  
- [Tortoise TTS — community discussions & optimization repo](https://github.com/neonbjb/tortoise-tts) 
- [Coqui TTS / XTTS (GitHub: coqui-ai/TTS)](https://github.com/coqui-ai/TTS) 


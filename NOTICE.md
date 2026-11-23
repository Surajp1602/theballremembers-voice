# Third-party notices

`ballvoice` is MIT-licensed. It depends on, or downloads, the following. None of them are copied into this repository.

| Component | Licence | How it's used |
|---|---|---|
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (hexgrad) | Apache-2.0 | The voice model. `ballvoice setup` downloads the ONNX export `kokoro-v1.0.onnx` and the style vectors `voices-v1.0.bin`. Apache-2.0 allows commercial use, including narration for a monetized channel. |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) (thewh1teagle) | MIT | Python package that runs the model with ONNX Runtime; its GitHub release hosts the two model files. |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) | GPL-3.0 | Phonemizer, installed by pip as a separate shared library through `espeakng-loader` and called at runtime. The audio you generate is not covered by its licence. |
| [phonemizer](https://github.com/bootphon/phonemizer) | GPL-3.0 | Python wrapper around espeak-ng, a dependency of kokoro-onnx. |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT | Inference engine. |
| [NumPy](https://numpy.org), [soundfile](https://github.com/bastibe/python-soundfile) | BSD-3-Clause | Audio arrays and WAV files. |
| [nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts) | MIT | Inspiration and reference: the kokoro-onnx approach, the v1.0 model files and the `voice:weight` blend syntax. No code copied. |

Model file checksums (SHA-256), checked by `ballvoice setup`:

```
7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5  kokoro-v1.0.onnx
bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d  voices-v1.0.bin
```

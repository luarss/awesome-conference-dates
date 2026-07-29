# 📅 Awesome Conference Dates

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🎯 **Your one-stop solution for tracking AI and VLSI conference deadlines in a unified calendar format**

A Python tool that aggregates conference deadlines from multiple sources and generates a unified ICS calendar file. Perfect for researchers, academics, and professionals who need to stay on top of important conference submission deadlines.

## ✨ Sources

Deadlines are fetched, normalised, and deduplicated across four sources:

- 🤖 **AI conferences** — [Hugging Face `ai-deadlines`](https://github.com/huggingface/ai-deadlines) (raw YAML)
- 🔬 **EDA / architecture venues** — [`ccfddl/ccf-deadlines`](https://github.com/ccfddl/ccf-deadlines)
- ⚡ **VLSI / circuits venues** — [IEEE CAS](https://ieee-cas.org/) conference list (direct data endpoint)
- 📝 **Gap venues** — [WikiCFP](http://www.wikicfp.com/) (e.g. ISPD, Euromicro DSD)

Each run also prints a **coverage report** against the tracked VLSI venue list and runs **sanity checks** (minimum entry/event counts, no duplicate UIDs, ICS round-trip validation), exiting non-zero on failure.

## 🚀 Quick Start

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/luarss/awesome-conference-dates.git
cd awesome-conference-dates

# Install dependencies
uv sync

# Generate the latest conference calendar
uv run python get_deadlines.py
```

The script generates an `output.ics` file that you can import into any calendar application.

## 📱 Live Calendar Feed

🔗 **Direct ICS Link**: [https://raw.githubusercontent.com/luarss/awesome-conference-dates/main/output.ics](https://raw.githubusercontent.com/luarss/awesome-conference-dates/main/output.ics)

Simply add this URL to your calendar application to get automatic daily updates!

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Hugging Face `ai-deadlines`](https://github.com/huggingface/ai-deadlines) for AI conference data
- [`ccfddl/ccf-deadlines`](https://github.com/ccfddl/ccf-deadlines), [IEEE CAS](https://ieee-cas.org/), and [WikiCFP](http://www.wikicfp.com/) for VLSI conference information

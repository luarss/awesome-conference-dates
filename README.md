# 📅 Awesome Conference Dates

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🎯 **Your one-stop solution for tracking AI and VLSI conference deadlines in a unified calendar format**

A Python tool that aggregates conference deadlines from multiple sources and generates a unified ICS calendar file. Perfect for researchers, academics, and professionals who need to stay on top of important conference submission deadlines.

## ✨ Features

- 🤖 **AI Conference Deadlines** - Fetches from [ai-deadlin.es](https://aideadlin.es/calendar/?sub=ML)
- 🔬 **VLSI Conference Deadlines** - Comprehensive data from [IEEE CAS](https://ieee-cas.org/conference-events/full-conference-list)

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/luarss/awesome-conference-dates.git
cd awesome-conference-dates

# Install dependencies
pip install -e .
```

### Usage

```bash
# Generate the latest conference calendar
python get_deadlines.py
```

The script will generate an `output.ics` file that you can import into any calendar application.

## 📱 Live Calendar Feed

🔗 **Direct ICS Link**: [https://raw.githubusercontent.com/luarss/awesome-conference-dates/main/output.ics](https://raw.githubusercontent.com/luarss/awesome-conference-dates/main/output.ics)

Simply add this URL to your calendar application to get automatic updates!

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [ai-deadlin.es](https://aideadlin.es/) for AI conference data
- [IEEE CAS](https://ieee-cas.org/) for VLSI conference information

---

**Note**: VLSI data from Chalmers University of Technology source is now deprecated.

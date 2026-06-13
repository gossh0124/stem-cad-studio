# stem-cad-studio

**An open-source, end-to-end AI-assisted hardware design platform for STEM education.**

stem-cad-studio takes free-form natural language input and generates physically printable STEM teaching aids — producing 3D CAD enclosures, PCB layouts, and microcontroller firmware in a single automated pipeline.

> **Core Thesis Proposition:** *Free-form input → Printable STEM teaching aids × 6E instructional model × Cross-four-domain learning (circuits, HCI, 3D design, software-hardware integration)*

## What This Project Does

A student or educator describes what they want to build in plain language. The system:

1. **Parses** the intent through a CAD Domain-Specific Language (DSL) designed for LLM-friendly geometric control
2. **Generates** a complete hardware package: 3D-printable enclosure, PCB layout, and matching firmware
3. **Verifies** every output through a multi-layer automated verification pipeline (L0–L3) — no silent failures, no hallucinated parameters
4. **Outputs** files ready for consumer-grade 3D printers and off-the-shelf components

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Natural Language Input                 │
└──────────────────────────┬──────────────────────────────┘
                           ▼
              ┌────────────────────────┐
              │     CAD DSL Engine     │
              │  (Domain-Specific Lang)│
              └─────────┬──────────────┘
                        ▼
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  ┌───────────┐  ┌────────────┐  ┌────────────┐
  │  3D CAD   │  │    PCB     │  │  Firmware  │
  │ Enclosure │  │   Layout   │  │ Generator  │
  │ Generator │  │  (Routing) │  │            │
  └─────┬─────┘  └─────┬──────┘  └─────┬──────┘
        │               │               │
        └───────────────┼───────────────┘
                        ▼
           ┌────────────────────────┐
           │   Assembly Solver      │
           │  (Packing, Collision,  │
           │   Thermal Analysis)    │
           └─────────┬──────────────┘
                     ▼
        ┌────────────────────────────┐
        │  Multi-Layer Verification  │
        │  L0: Data Integrity        │
        │  L1: Geometry / Netlist    │
        │  L2: PCB Layout            │
        │  L3: Assembly Validation   │
        └────────────────────────────┘
                     ▼
           ┌──────────────────┐
           │  Printable Output │
           │  STL + Gerber +   │
           │  .ino / .py       │
           └──────────────────┘
```

## Key Design Principles

- **No-Silent-Fallback:** Every anomaly raises an error. The system never silently degrades or substitutes hallucinated values. If a generated design violates physical constraints, the pipeline stops and reports — it does not guess.
- **Single Source of Truth (SSOT):** All component specifications (pin maps, dimensions, voltage domains, thermal limits) are grounded in a verified datasheet database. Generated designs are traceable back to authoritative data.
- **Hierarchical LLM Planning:** Inspired by the CAD-HLLM framework (Zuo et al., ACML 2025), the system decomposes text-to-hardware generation into coarse symbolic planning followed by parametric completion — extended beyond pure CAD into PCB, firmware, and assembly.

## Supported Hardware Platforms

| MCU Platform | Example Demos |
|---|---|
| Arduino Uno | auto_waterer, smart_nightlight, electronic_keyboard |
| Arduino Nano | biped_robot |
| Micro:bit | plant_monitor |
| ESP32 | access_control |

The system includes 16 template projects with **6 core validated demos** spanning 4 MCU platforms, each designed to be reproducible with consumer-grade 3D printers and off-the-shelf components.

## Verification Pipeline

The system enforces correctness at four levels:

| Level | Check | What It Catches |
|---|---|---|
| **L0** | Data Integrity | Missing fields, schema violations, SSOT drift |
| **L1** | Geometry & Netlist | Collision detection, bounding box interference, circuit connectivity |
| **L2** | PCB Layout | Routing validity, clearance rules, power rail feasibility |
| **L3** | Assembly | Physical fit, thermal envelope (PLA Tg threshold), snap-fit analysis |

## Tech Stack

- **Backend:** Python (FastAPI microservices, vLLM client for local model inference)
- **Frontend:** React/JSX interactive visualization with preset project library
- **AI Integration:** Claude API (primary reasoning), local vLLM (auxiliary tasks)
- **CAD Engine:** build123d / OpenCascade (OCP) for parametric 3D modeling
- **Verification:** 6,000+ automated tests, multi-layer validation pipeline

## Academic Context

This project is being developed as a master's thesis at the Graduate Institute of Mathematics and Information Education, National Taipei University of Education (NTUE), under the supervision of Prof. Chien-Hsing Chou. The thesis investigates how AI-assisted hardware generation can support the 6E instructional model across four learning domains.

The generation core draws from the **CAD-HLLM** framework:
> Zuo, Z., Gan, Y., Long, J., & Liu, X. (2025). *CAD-HLLM: Generating Executable CAD from Text with Hierarchical LLM Planning.* Proceedings of Machine Learning Research 304, ACML 2025.

## Project Status

- ✅ Core architecture complete (V3 rewrite with 729-commit history)
- ✅ 6 core demos validated across 4 MCU platforms
- ✅ L0–L3 verification pipeline operational
- ✅ 6,000+ automated tests passing
- 🔄 Educational effectiveness study (Ch5 pre/post-test) in design phase
- 🔄 Documentation and community onboarding materials

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**Po-Han Su (蘇柏翰)**
- M.S. Student, AI Track — National Taipei University of Education
- Previously: B.S. Electrical Engineering (Information Track), Tamkang University
- Previously: Junior BIOS Firmware Engineer, Insyde Software

## Acknowledgments

- Prof. Chien-Hsing Chou (周建興) for advising this research and providing funding support
- National Taipei University of Education for institutional support
- Anthropic for Claude — the primary AI reasoning engine powering this system

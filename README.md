# HiveBox 🐝

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Passw0rd404/HiveBox/badge)

> A containerized FastAPI application for temperature monitoring and version management with advanced security features. Deploy with Docker in seconds!

## 📊 OpenSSF Scorecard Report

This project maintains security best practices as measured by the OpenSSF Scorecard. OpenSSF launched Scorecard in November 2020 with the intention of auto-generating a "security score" for open source projects to help users as they decide the trust, risk, and security posture for their use case.

### Current Security Score
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Passw0rd404/HiveBox/badge)](https://scorecard.dev/viewer/?uri=github.com/Passw0rd404/HiveBox)

To view the detailed security assessment:
- **Scorecard Report**: [View Full Report](https://scorecard.dev/viewer/?uri=github.com/Passw0rd404/HiveBox)
- **Badge URL**: `https://api.scorecard.dev/projects/github.com/Passw0rd404/HiveBox/badge`

## 🚀 Features

- **Temperature Monitoring API**: RESTful endpoints for temperature data management
- **Version Control**: API versioning and version information endpoints
- **Security Focused**: Implements security best practices as measured by OpenSSF Scorecard
- **FastAPI Framework**: Built with FastAPI for high-performance, modern API development
- **Automatic Documentation**: Interactive API docs with Swagger UI and ReDoc
- **Type Safety**: Full type hints for better development experience
- **Modular Architecture**: Clean separation of concerns with organized endpoints

## 📁 Project Structure

```
HiveBox/
├── scr/                    # Source code directory
│   ├── main.py            # Main FastAPI application entry point
│   └── endpoints/         # API endpoints
│       ├── temperature.py # Temperature monitoring endpoints
│       └── version.py     # Version information endpoints
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## 🛠 Installation & Deployment

### Prerequisites
- Docker and Docker Compose
- Git

### Quick Start with Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/Passw0rd404/HiveBox.git
   cd HiveBox
   ```

2. **Build and run with Docker**
   ```bash
   # Build the Docker image
   docker build -t hivebox .

   # Run the container
   docker run -p 8000:8000 hivebox
   ```

3. **Or use Docker Compose**
   ```bash
   docker-compose up --build
   ```

### Alternative: Local Development Setup

If you prefer to run locally for development:

1. **Clone the repository**
   ```bash
   git clone https://github.com/Passw0rd404/HiveBox.git
   cd HiveBox
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies from requirements.txt**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python -m scr.main
   ```

The application will be available at:
- **API**: `http://localhost:8000`

## 🔧 Usage

### API Endpoints

#### Temperature Endpoints
- `GET /temperature` - Retrieve temperature data

#### Version Endpoints
- `GET /version` - Get current API version

### Example Requests

```bash
# Get temperature data
curl -X GET http://localhost:8000/api/temperature

# Get version information
curl -X GET http://localhost:8000/api/version
```

## 🔒 Security

This project follows security best practices and is regularly assessed using OpenSSF Scorecard. Each project is evaluated against these security checks and receives a score (on a scale of 0 to 10) that reflects the overall security maturity of the project.

### Security Features
- Secure error handling
- Regular dependency updates
- Automated security scanning

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- DevOps Roadmap for comprehensive DevOps learning resources [https://devopsroadmap.io/]
- Ahmed AbouZaid for guidance [https://www.linkedin.com/in/aabouzaid/]
- All contributors who help improve this project

## 📊 Project Status

![GitHub last commit](https://img.shields.io/github/last-commit/Passw0rd404/HiveBox)
![GitHub issues](https://img.shields.io/github/issues/Passw0rd404/HiveBox)
![GitHub pull requests](https://img.shields.io/github/issues-pr/Passw0rd404/HiveBox)

---

**Maintained with ❤️ by [Passw0rd404](https://github.com/Passw0rd404)**

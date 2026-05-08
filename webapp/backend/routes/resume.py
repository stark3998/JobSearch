from __future__ import annotations

import logging
import re
import shutil
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..models import ResumeRequest, ResumeResponse, ValidationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])

REPO_ROOT = Path(__file__).resolve().parents[3]
FILTERED_DIR = REPO_ROOT / "pipeline_output" / "filtered"
ANALYSIS_DIR = REPO_ROOT / "pipeline_output" / "analyses"
RESUMES_DIR = REPO_ROOT / "Resumes"
COVER_LETTERS_DIR = REPO_ROOT / "CoverLetters"
BASE_TEX = REPO_ROOT / "Base" / "cv.tex"


def _find_latest_csv(directory: Path, prefix: str):
    files = sorted(directory.glob(f"{prefix}*.csv"), reverse=True)
    return files[0] if files else None


def _slugify(text):
    if not text or pd.isna(text):
        return "unknown"
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:50].strip("-")


def _migrate_flat_archive():
    """One-time migration: move flat archive files into company subfolders."""
    archive_base = RESUMES_DIR / "archive"
    if not archive_base.exists():
        return
    for f in list(archive_base.iterdir()):
        if f.is_file() and (f.name.startswith("cv_") or f.name.startswith("coverletter_")):
            prefix = "cv_" if f.name.startswith("cv_") else "coverletter_"
            slug = f.stem.replace(prefix, "")
            dest_dir = archive_base / slug
            dest_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(f), str(dest_dir / f.name))
            except Exception as e:
                logger.warning(f"Failed to migrate archive file {f.name}: {e}")


def _archive_existing(target_company_slug: str | None = None):
    """Move current resume/cover-letter files to structured archive folders."""
    archive_base = RESUMES_DIR / "archive"
    archive_base.mkdir(parents=True, exist_ok=True)

    for f in list(RESUMES_DIR.iterdir()):
        if not f.is_file() or not f.name.startswith("cv_"):
            continue
        slug = f.stem.replace("cv_", "")
        dest_dir = archive_base / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(f), str(dest_dir / f.name))
        except Exception as e:
            logger.warning(f"Failed to archive {f.name}: {e}")

    if COVER_LETTERS_DIR.exists():
        for f in list(COVER_LETTERS_DIR.iterdir()):
            if not f.is_file() or not f.name.startswith("coverletter_"):
                continue
            slug = f.stem.replace("coverletter_", "")
            dest_dir = archive_base / slug
            dest_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(f), str(dest_dir / f.name))
            except Exception as e:
                logger.warning(f"Failed to archive {f.name}: {e}")


# ---------------------------------------------------------------------------
# LaTeX content per archetype — from CLAUDE.md Sections 8.3–8.6
# ---------------------------------------------------------------------------

PREAMBLE = r"""% article class because we want to fully customize the page and not use a cv template
\documentclass[a4paper,3pt]{article}

%----------------------------------------------------------------------------------------
%	PACKAGES
%----------------------------------------------------------------------------------------
\usepackage{url}
\usepackage{parskip}

%other packages for formatting
\RequirePackage{color}
\RequirePackage{graphicx}
\usepackage[usenames,dvipsnames]{xcolor}
\usepackage[scale=0.95]{geometry}

%tabularx environment
\usepackage{tabularx}

% longtable environment
\usepackage{longtable}

%for lists within experience section
\usepackage{enumitem}

% centered version of 'X' col. type
\newcolumntype{C}{>{\centering\arraybackslash}X}

%to prevent spillover of tabular into next pages
\usepackage{supertabular}
\usepackage{tabularx}
\newlength{\fullcollw}
\setlength{\fullcollw}{0.47\textwidth}

%custom \section
\usepackage{titlesec}
\usepackage{multicol}
\usepackage{multirow}
\usepackage{ifsym}

%CV Sections inspired by:
%http://stefano.italians.nl/archives/26
\titleformat{\section}{\Large\scshape\raggedright}{}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{0pt}{6pt}

%for publications
\usepackage[style=authoryear,sorting=ynt, maxbibnames=2]{biblatex}

%Setup hyperref package, and colours for links
\usepackage[unicode, draft=false]{hyperref}
\definecolor{linkcolour}{rgb}{0,0.2,0.5}
\hypersetup{colorlinks,breaklinks,urlcolor=linkcolour,linkcolor=linkcolour}
\addbibresource{citations.bib}
\setlength\bibitemsep{1em}

%for social icons
\usepackage{fontawesome5}

%----------------------------------------------------------------------------------------
%	BEGIN DOCUMENT
%----------------------------------------------------------------------------------------
\begin{document}

% non-numbered pages
\pagestyle{empty}

%----------------------------------------------------------------------------------------
%	TITLE
%----------------------------------------------------------------------------------------

\begin{tabularx}{\linewidth}{@{} C @{}}
    \Huge{Jatin Madan}                                                           \\[10.5pt]
    \href{https://github.com/stark3998}{\raisebox{-0.05\height}\faGithub\ stark3998} \ $|$ \
    \href{https://linkedin.com/in/jatin39}{\raisebox{-0.05\height}\faLinkedin\ Jatin39} \ $|$ \
    \href{https://jatinmadan.com}{\raisebox{-0.05\height}\faGlobe \ jatinmadan.com} \ $|$ \
    \href{mailto:jatin.madan39@gmail.com}{\raisebox{-0.05\height}\faEnvelope \ jatin.madan39@gmail.com} \ $|$ \
    \href{tel:+19492139330}{\raisebox{-0.05\height}\faMobile \ +1(949)-213-9330} \\
\end{tabularx}
%----------------------------------------------------------------------------------------
%	EDUCATION
%----------------------------------------------------------------------------------------

\begin{tabularx}{\linewidth}{ @{}l r@{} }
    \textbf{University of California, Irvine} | Master of Computer Science | GPA: 4.0            & \hfill [Irvine, CA, USA] Sept 2023 - Dec 2024 \\[2pt]
    \textbf{Vellore Institute of Technology} | B.Tech Computer Science and Engineering & \hfill [Vellore, India] July 2016 - June 2020 \\[2pt]
\end{tabularx}
"""

SKILLS_TEMPLATES = {
    "cloud_security": r"""\section{Skills}
\begin{tabularx}{\linewidth}{@{}l X@{}}
    Languages/Scripts     & \normalsize{\textbf{Python, C\#, PowerShell, Bash,} SQL, Java, JavaScript}\\
    Security \& DevSecOps & \normalsize{\textbf{CSPM, CWPP, CIEM, SIEM, Zero Trust, IAM/RBAC,} Conditional Access, Vulnerability Management, Defender for Cloud, Sentinel, Purview, CIS, NIST, MCSB}\\
    Tools/IaC             & \normalsize{\textbf{Terraform, Bicep, Docker, Kubernetes (AKS),} Azure DevOps, Jenkins, GitHub Actions, GHAS}\\
    Cloud Stack           & \normalsize{\textbf{Azure} (PaaS/IaaS: full stack), \textbf{AWS} (S3, Lambda), Multi-Cloud Security Architecture}\\
\end{tabularx}
""",
    "security_architecture": r"""\section{Skills}
\begin{tabularx}{\linewidth}{@{}l X@{}}
    Languages/Scripts      & \normalsize{\textbf{Python, C\#, PowerShell, Bash,} SQL, Java, JavaScript}\\
    Security Architecture  & \normalsize{\textbf{Threat Modeling, Attack Surface Analysis, Security Architecture Reviews, Reference Architecture Design, Zero Trust,} Secure Design Patterns, API Security, Secrets Management, Encryption, Authentication/Authorization, Pipeline Security, NIST, ISO 27001, CSA, MCSB, CIS}\\
    Cloud \& DevSecOps     & \normalsize{\textbf{Azure, AWS, GCP,} Multi-Cloud Security, Serverless, \textbf{Kubernetes (AKS),} Docker, Terraform, Azure DevOps, CI/CD Pipeline Security, CSPM, CWPP, Sentinel, Defender for Cloud, Purview}\\
    Tools                  & \normalsize{Databricks, Power BI, Postman, PySpark, Pandas, NLTK, Django}\\
\end{tabularx}
""",
    "software_security": r"""\section{Skills}
\begin{tabularx}{\linewidth}{@{}l X@{}}
    Languages           & \normalsize{\textbf{Python, C\#, PowerShell, Bash,} SQL, Java, JavaScript, Swift}\\
    Security Engineering & \normalsize{\textbf{Workload Identity (OIDC, OAuth 2.0, SAML), Secrets Management, RBAC, Kubernetes Security} (Namespaces, Network Policies, Admission Controllers, Pod Security), \textbf{CI/CD Supply Chain Security} (GHAS, Signed Attestations, Dependency Verification), SAST, IaC Security Scanning, Zero Trust, Threat Modeling, CSPM}\\
    Cloud \& Infra      & \normalsize{\textbf{Azure} (AKS, Key Vault, Entra ID, Function Apps, VNet, Log Analytics, VMSS), \textbf{AWS} (S3, Lambda), \textbf{Multi-Cloud IAM}, VPC Architecture, Network Segmentation, \textbf{Terraform, Bicep, Docker, Kubernetes}, GitHub Actions, Azure DevOps}\\
    Tools               & \normalsize{Microsoft Sentinel, Defender for Cloud, Purview, Databricks, Power BI, Postman, PySpark, Pandas, NLTK, Django}
\end{tabularx}
""",
    "cloud_devops": r"""\section{Skills}
\begin{tabularx}{\linewidth}{@{}l X@{}}
    Languages/Scripts  & \normalsize{\textbf{Python, C\#, ASP .Net, PowerShell,} SQL, Bash, YAML, Java, JavaScript}\\
    IaC \& DevOps      & \normalsize{\textbf{Terraform, Bicep, GitHub Actions, GitHub Copilot, GHAS}, Azure DevOps, Jenkins, \textbf{Docker, Kubernetes (AKS, GKE)}, Artifactory, CI/CD Pipeline Design, Agile (Scrum, Kanban)}\\
    Cloud Platforms    & \normalsize{\textbf{Azure} (PaaS/IaaS: Storage, Function Apps, Web Apps, Event Hubs, Service Bus, Log Analytics, VMSS, AKS, Container Instances, SQL, Cosmos DB, Key Vault), \textbf{GCP} (GKE, BigQuery, Google Workspace), \textbf{AWS} (S3, Lambda)}\\
    Monitoring \& Cost & \normalsize{\textbf{Dynatrace, Grafana, Datadog}, Azure Monitor, Log Analytics, Power BI, \textbf{Cloud Cost Optimization}, SLA Tracking, Resource Trend Reporting, Vulnerability Management, CSPM}
\end{tabularx}
""",
}

EXPERIENCE_BULLETS = {
    "cloud_security": {
        "deloitte_us": [
            r"\item[--] Architected and deployed \textbf{fully automated IaC solutions} using \textbf{Terraform and Bicep} across \textbf{Azure PaaS and IaaS environments}, enforcing \textbf{enterprise-wide cloud platform standards} for security, cost, and compliance across \textbf{5+ business units and 150K+ users}",
            r"\item[--] Built and maintained \textbf{CI/CD pipelines} using \textbf{GitHub Actions and Azure DevOps}, integrating \textbf{GitHub Advanced Security (GHAS)} and \textbf{automated IaC compliance scanning} to enforce standardized security tooling across all deployment workflows",
            r"\item[--] Onboarded \textbf{2,000+ enterprise applications and 120K+ identities} into \textbf{cloud IaC environments}, providing \textbf{technical support at design and operational phases} and resolving cloud configuration, networking, and identity issues within defined SLAs",
            r"\item[--] Implemented \textbf{cloud monitoring and observability} using \textbf{Azure Monitor, Log Analytics, and Power BI dashboards}, producing \textbf{periodic reports on resource usage, cost trends, and platform performance} to guide strategic architecture decisions",
            r"\item[--] Contributed to \textbf{continuous CSPM} using \textbf{Terraform IaC scanning, misconfiguration detection, and automated remediation} -- identified gaps through code review and threat modeling, shipped fixes, and maintained \textbf{100\% policy compliance} across multi-cloud production environments",
            r"\item[--] Led \textbf{cross-functional working groups} across delivery and platform teams, driving \textbf{cloud cost optimization initiatives} and establishing \textbf{secure-by-default IaC guardrails and cloud platform standards}",
        ],
        "zs": [
            r"\item[--] Overhauled \textbf{ETL workflows} by converting \textbf{3,000 Parquet tables to Delta tables} using \textbf{Apache Spark and Databricks}, leveraging \textbf{Azure Data Factory pipelines} to enhance scalability and cloud platform efficiency",
            r"\item[--] Designed and published a \textbf{hardened custom Docker image} for Databricks clusters via \textbf{Artifactory}, reducing cluster runtime by \textbf{14\%} by eliminating runtime package installations",
            r"\item[--] Implemented \textbf{Unity Catalog} in Databricks for \textbf{unified data governance}, using \textbf{Azure Key Vault and ADLS fine-grained access controls} to enforce compliance; produced \textbf{Grafana dashboards} tracking data pipeline health",
        ],
        "uci": [
            r"\item[--] Engineered \textbf{hybrid cloud infrastructure} using \textbf{Terraform IaC}, deploying \textbf{Application Proxy, Entra ID Connect, F5 load balancing, firewall, and DNS routing} -- troubleshooting cloud networking, configuration, and authentication issues",
            r"\item[--] Built an \textbf{Apple Vision OS remote development platform} (SwiftUI, SSH, VS Code Server) running on \textbf{Azure-hosted infrastructure}, collaborating with application and platform teams to maintain \textbf{stable cloud environments}",
            r"\item[--] Produced \textbf{technical documentation and architecture presentations} for stakeholders at all organizational levels, communicating cloud platform design decisions and infrastructure standards",
        ],
        "deloitte_india": [
            r"\item[--] Designed and deployed \textbf{fully automated cloud solutions} on Azure (\textbf{VMSS, AKS, App Service, Cosmos DB, Redis Cache, Event Hubs}) using \textbf{Terraform IaC and Azure DevOps pipelines}, supporting enterprise workloads across \textbf{IaaS, PaaS, and SaaS}",
            r"\item[--] Developed an \textbf{Azure DevOps extension} to \textbf{pre-scan Terraform IaC templates} for misconfigurations and policy violations before deployment, integrating findings into \textbf{Power BI dashboards} for resource trend reporting",
            r"\item[--] Analyzed \textbf{cloud usage patterns and cost trends} across multi-cloud environments, producing \textbf{periodic reports and Grafana/Power BI dashboards} to guide \textbf{strategic architecture decisions}",
            r"\item[--] Onboarded enterprise value streams into \textbf{cloud IaC environments}, providing \textbf{technical support at design and operational phases}, troubleshooting \textbf{cloud service, networking, and configuration issues}",
            r"\item[--] Built \textbf{ETL workflows} with \textbf{Azure Synapse, Azure SQL, and Azure Data Factory}, collaborating cross-functionally with application, infrastructure, and security teams",
        ],
    },
    "security_architecture": {
        "deloitte_us": [
            r"\item[--] Architected \textbf{secure-by-default cloud platform standards} using \textbf{Terraform and Bicep IaC}, producing \textbf{reusable reference architectures} enforcing security, cost, and compliance guardrails across \textbf{5+ business units and 150K+ users}",
            r"\item[--] Conducted \textbf{threat modeling and attack surface analysis} across API, identity, serverless, and containerized attack vectors -- acting as security SME for engineering teams and presenting findings to Architecture Review Board",
            r"\item[--] Implemented \textbf{AI security and governance frameworks} including \textbf{red-teaming, model guardrails, and policy-driven monitoring} via \textbf{Purview and Defender for Cloud}, reducing \textbf{AI security risks by 45\%} across enterprise AI deployments",
            r"\item[--] Designed \textbf{IaC security guardrails and Terraform-based migration accelerators}, achieving \textbf{100\% policy compliance} across production environments and establishing \textbf{secure-by-default CI/CD pipeline patterns}",
            r"\item[--] Led \textbf{cross-functional security working groups} across delivery and platform teams, producing \textbf{formal risk assessments} and \textbf{security architecture reviews} based on NIST, ISO 27001, and MCSB frameworks",
            r"\item[--] Mentored junior engineers and participated in \textbf{Architecture Review Board}, defining \textbf{cloud security reference designs and standards} for enterprise adoption",
        ],
        "zs": [
            r"\item[--] Performed \textbf{data security architecture review} -- identified access control gaps, privilege escalation paths, and misconfigurations across \textbf{3,000+ datasets}; produced formal risk findings with remediation guidance",
            r"\item[--] Built and published a \textbf{hardened Docker image} via \textbf{Artifactory} with security-vetted packages, eliminating runtime installation attack surface and reducing provisioning time by \textbf{14\%}",
            r"\item[--] Implemented \textbf{Unity Catalog} in Databricks with \textbf{fine-grained RBAC, encryption, and audit logging} across \textbf{Azure Data Lake Storage} -- enforcing least-privilege access controls",
        ],
        "uci": [
            r"\item[--] Engineered a \textbf{hybrid identity architecture} using \textbf{Entra ID Connect, OIDC federation, Application Proxy, and HRD policies} -- producing \textbf{architecture documentation} for stakeholders and resolving cross-provider authentication issues",
            r"\item[--] Conducted \textbf{threat modeling} of hybrid identity environment -- identified authentication attack vectors including session hijacking, token replay, and lateral movement risks",
            r"\item[--] Produced \textbf{technical documentation and architecture presentations} at all organizational levels, communicating cloud platform design decisions, infrastructure standards, and implementation guidance",
        ],
        "deloitte_india": [
            r"\item[--] Architected and deployed \textbf{Zero Trust security} within Azure -- integrating \textbf{Entra ID governance, RBAC, identity lifecycle management, conditional access, network segmentation, VPC architecture, and encryption}",
            r"\item[--] Designed \textbf{Zero Trust reference architectures} as reusable secure design patterns for enterprise adoption, establishing \textbf{Cloud Governance processes and standard operating procedures}",
            r"\item[--] Built an \textbf{Automated Multi-Cloud Security Assessment Tool} in \textbf{Python} scanning for \textbf{IAM misconfigurations, network segmentation gaps, and RBAC violations} -- reducing manual effort by \textbf{78\%}",
            r"\item[--] Conducted \textbf{application penetration testing and code-level auditing} of PaaS databases and Kubernetes clusters -- discovered privilege escalation, insecure deserialization, and lateral movement vulnerabilities",
        ],
    },
    "software_security": {
        "deloitte_us": [
            r"\item[--] Built and shipped an \textbf{MCP server on AKS} implementing \textbf{OIDC-based workload identity, credential rotation, and secrets management via Azure Key Vault} -- enabling secure service-to-service \textbf{Microsoft Graph API} operations end-to-end",
            r"\item[--] Engineered \textbf{Kubernetes cluster security controls} including \textbf{RBAC policies, namespace isolation, pod security standards, network policies, and admission controllers} across multi-tenant AKS environments supporting \textbf{150K+ user} workloads",
            r"\item[--] Hardened \textbf{CI/CD pipelines} against supply chain attacks by integrating \textbf{GitHub Advanced Security (GHAS), signed attestations, dependency verification, automated IaC scanning, and policy enforcement} across \textbf{2,000+ application} deployment pipelines",
            r"\item[--] Developed \textbf{secure development libraries and migration accelerators} in \textbf{Python and PowerShell} -- standardizing \textbf{credential issuance, RBAC configuration, and identity replication} across Entra ID tenants, reducing manual effort by \textbf{70\%}",
            r"\item[--] Implemented \textbf{AI security and governance frameworks} including \textbf{red-teaming, model guardrails, and policy-driven monitoring} via \textbf{Purview and Defender for Cloud}, reducing \textbf{AI security risks by 45\%}",
            r"\item[--] Contributed to \textbf{continuous CSPM} using \textbf{Terraform IaC scanning, misconfiguration detection, and automated remediation} -- maintained \textbf{100\% policy compliance} across multi-cloud production environments",
        ],
        "zs": [
            r"\item[--] Implemented \textbf{Unity Catalog} in Databricks with \textbf{fine-grained RBAC, encryption, and audit logging} across \textbf{Azure Data Lake Storage} -- took ownership end-to-end from identifying access control gaps to shipping the governance solution across 3,000+ tables",
            r"\item[--] Built and published a \textbf{hardened Docker image} via \textbf{Artifactory} with security-vetted, pre-installed packages, eliminating runtime installation attack surface and reducing provisioning time by \textbf{14\%}",
            r"\item[--] Identified and remediated \textbf{cloud security misconfigurations} through hands-on infrastructure code review, producing documented findings and collaborating with the platform team to ship fixes within the sprint cycle",
        ],
        "uci": [
            r"\item[--] Engineered a \textbf{hybrid workload identity system} using \textbf{Entra ID Connect, OIDC federation, Application Proxy, and HRD policies} -- implemented \textbf{credential issuance and rotation} patterns across a multi-provider environment",
            r"\item[--] Built an \textbf{Apple Vision OS remote development platform} in \textbf{Swift} (SSH tunneling, VS Code Server, sandboxed execution) -- designed with \textbf{secure credential management and network isolation} as first-class requirements",
            r"\item[--] Performed \textbf{threat modeling and hands-on debugging} of authentication and session flows, identified token replay and session hijacking vectors, and shipped fixes validated through code review",
        ],
        "deloitte_india": [
            r"\item[--] Built an \textbf{Automated Multi-Cloud Security Assessment Tool} in \textbf{Python} scanning for \textbf{IAM misconfigurations, network segmentation gaps, and RBAC violations} -- reducing manual effort by \textbf{78\%} and improving misconfiguration detection by \textbf{35\%}",
            r"\item[--] Implemented \textbf{Zero Trust network architecture} in Azure -- engineering \textbf{VPC segmentation, east-west traffic controls, IAM policy enforcement, encryption in transit and at rest, and VNet isolation}",
            r"\item[--] Developed an \textbf{Azure DevOps IaC scanning extension in Python} that \textbf{pre-scanned Terraform templates} for supply chain policy violations and misconfigurations before deployment",
            r"\item[--] Overhauled \textbf{Kubernetes and PaaS IAM} by automating \textbf{RBAC role mapping, secrets rotation, and identity lifecycle management} via \textbf{Python and PowerShell} tooling",
            r"\item[--] Shipped a \textbf{Secure SSO system} and \textbf{Video Conferencing Platform} applying \textbf{OAuth 2.0 authentication, API security controls, and serialization hardening}",
        ],
    },
    "cloud_devops": {
        "deloitte_us": [
            r"\item[--] Architected and deployed \textbf{fully automated IaC solutions} using \textbf{Terraform and Bicep} across \textbf{Azure PaaS and IaaS environments}, enforcing \textbf{enterprise-wide cloud platform standards} for security, cost, and compliance across \textbf{5+ business units and 150K+ users}",
            r"\item[--] Built and maintained \textbf{CI/CD pipelines} using \textbf{GitHub Actions and Azure DevOps}, integrating \textbf{GitHub Advanced Security (GHAS)} and \textbf{automated IaC compliance scanning} to enforce standardized security tooling across all deployment workflows",
            r"\item[--] Onboarded \textbf{2,000+ enterprise applications and 120K+ identities} into \textbf{cloud IaC environments}, providing \textbf{technical support at design and operational phases} and resolving cloud configuration, networking, and identity issues within defined SLAs",
            r"\item[--] Implemented \textbf{cloud monitoring and observability} using \textbf{Azure Monitor, Log Analytics, and Power BI dashboards}, producing \textbf{periodic reports on resource usage, cost trends, and platform performance} to guide strategic architecture decisions",
            r"\item[--] Developed an \textbf{MCP server on Azure Kubernetes Service (AKS)}, troubleshooting \textbf{networking, configuration, and infrastructure issues} across containerized workloads and collaborating with cross-functional platform and application teams to maintain SLA adherence",
            r"\item[--] Led \textbf{cross-functional working groups} across delivery and platform teams, driving \textbf{cloud cost optimization initiatives} and establishing \textbf{secure-by-default IaC guardrails and cloud platform standards}",
        ],
        "zs": [
            r"\item[--] Overhauled \textbf{ETL workflows} by converting \textbf{3,000 Parquet tables to Delta tables} using \textbf{Apache Spark and Databricks}, leveraging \textbf{Azure Data Factory pipelines} and \textbf{BigQuery-compatible} data patterns to enhance scalability",
            r"\item[--] Designed and published a \textbf{hardened custom Docker image} for Databricks clusters via \textbf{Artifactory}, reducing cluster runtime by \textbf{14\%} by eliminating runtime package installations",
            r"\item[--] Implemented \textbf{Unity Catalog} in Databricks for \textbf{unified data governance}, using \textbf{Azure Key Vault and ADLS fine-grained access controls}; produced \textbf{Grafana dashboards} tracking data pipeline health and resource utilization",
        ],
        "uci": [
            r"\item[--] Engineered \textbf{hybrid cloud infrastructure} using \textbf{Terraform IaC}, deploying \textbf{Application Proxy, Entra ID Connect, F5 load balancing, firewall, and DNS routing} -- troubleshooting cloud networking, configuration, and authentication issues across the enterprise platform",
            r"\item[--] Built an \textbf{Apple Vision OS remote development platform} (SwiftUI, SSH, VS Code Server) running on \textbf{Azure-hosted infrastructure}, collaborating with application and platform teams to maintain \textbf{stable cloud environments} and resolve incidents within agreed SLAs",
            r"\item[--] Produced \textbf{technical documentation and architecture presentations} for stakeholders at all organizational levels, communicating cloud platform design decisions, infrastructure standards, and implementation guidance in both \textbf{Agile sprint reviews and executive briefings}",
        ],
        "deloitte_india": [
            r"\item[--] Designed and deployed \textbf{fully automated cloud solutions} on Azure (\textbf{VMSS, AKS, App Service, Cosmos DB, Redis Cache, Event Hubs}) using \textbf{Terraform IaC and Azure DevOps pipelines}, supporting enterprise workloads across \textbf{IaaS, PaaS, and SaaS} configurations",
            r"\item[--] Developed an \textbf{Azure DevOps extension} to \textbf{pre-scan Terraform IaC templates} for misconfigurations and policy violations before deployment, integrating findings into \textbf{Power BI dashboards} for resource trend reporting and stakeholder-facing cost and compliance summaries",
            r"\item[--] Analyzed \textbf{cloud usage patterns and cost trends} across multi-cloud environments, producing \textbf{periodic reports and Grafana/Power BI dashboards} to guide \textbf{strategic architecture decisions} and drive \textbf{cloud cost optimization initiatives}",
            r"\item[--] Onboarded enterprise value streams into \textbf{cloud IaC environments}, providing \textbf{technical support at design and operational phases}, troubleshooting \textbf{cloud service, networking, and configuration issues}, and maintaining \textbf{platform SLA adherence}",
            r"\item[--] Built \textbf{ETL workflows} with \textbf{Azure Synapse, Azure SQL, and Azure Data Factory}, maintaining \textbf{working knowledge of Google and Azure platform services} and collaborating cross-functionally with application, infrastructure, and security teams",
        ],
    },
}

DELOITTE_US_TITLE = {
    "cloud_security": "Engineering Manager",
    "security_architecture": "Engineering Manager",
    "software_security": "Engineering Manager",
    "cloud_devops": "Engineering Manager",
}

DELOITTE_INDIA_TITLE = {
    "cloud_security": "Cloud Infrastructure Solution Advisor",
    "security_architecture": "Cyber Security Solution Advisor",
    "software_security": "Cyber Security Solution Advisor",
    "cloud_devops": "Cloud Infrastructure Solution Advisor",
}

CERTS = {
    "cloud_security": [
        (r"Azure Solutions Architect Expert", "AZ-304", "H693-3978", "Feb 21, 2021"),
        (r"DevOps Engineer Expert", "AZ-400", "H813-4148", "May 16, 2021"),
        (r"Azure Security Engineer Associate", "AZ-500", "H736-2347", "Mar 28, 2021"),
        (r"Azure Network Engineer Associate", "AZ-700", "I483-3372", "Nov 12, 2021"),
        (r"Azure Data Engineer Associate", "DP-203", "I094-4717", "Dec 29, 2021"),
    ],
    "security_architecture": [
        (r"Azure Security Engineer Associate", "AZ-500", "H736-2347", "Mar 28, 2021"),
        (r"Azure Solutions Architect Expert", "AZ-304", "H693-3978", "Feb 21, 2021"),
        (r"DevOps Engineer Expert", "AZ-400", "H813-4148", "May 16, 2021"),
        (r"Azure Developer Associate", "AZ-204", "H717-3092", "Mar 13, 2021"),
        (r"Azure AI Fundamentals", "AI-900", "H717-3092", "2021"),
    ],
    "software_security": [
        (r"Azure Security Engineer Associate", "AZ-500", "H736-2347", "Mar 28, 2021"),
        (r"Azure Solutions Architect Expert", "AZ-304", "H693-3978", "Feb 21, 2021"),
        (r"DevOps Engineer Expert", "AZ-400", "H813-4148", "May 16, 2021"),
        (r"Azure Developer Associate", "AZ-204", "H717-3092", "Mar 13, 2021"),
        (r"Azure Network Engineer Associate", "AZ-700", "I483-3372", "Nov 12, 2021"),
    ],
    "cloud_devops": [
        (r"Azure Solutions Architect Expert", "AZ-304", "H693-3978", "Feb 21, 2021"),
        (r"DevOps Engineer Expert", "AZ-400", "H813-4148", "May 16, 2021"),
        (r"Azure Security Engineer Associate", "AZ-500", "H736-2347", "Mar 28, 2021"),
        (r"Azure Network Engineer Associate", "AZ-700", "I483-3372", "Nov 12, 2021"),
        (r"Azure Data Engineer Associate", "DP-203", "I094-4717", "Dec 29, 2021"),
    ],
}

ARCHETYPE_DISPLAY = {
    "cloud_security": "Cloud Security Engineering",
    "security_architecture": "Security Architecture",
    "software_security": "Software Security Engineering",
    "cloud_devops": "Cloud DevOps / Platform Engineering",
}

CERTS_ALL = [
    (r"Azure Solutions Architect Expert", "AZ-304", "H693-3978", "Feb 21, 2021"),
    (r"DevOps Engineer Expert", "AZ-400", "H813-4148", "May 16, 2021"),
    (r"Azure Security Engineer Associate", "AZ-500", "H736-2347", "Mar 28, 2021"),
    (r"Azure Developer Associate", "AZ-204", "H717-3092", "Mar 13, 2021"),
    (r"Azure Data Engineer Associate", "DP-203", "---", "2021"),
    (r"Azure Network Engineer Associate", "AZ-700", "I483-3372", "Nov 12, 2021"),
    (r"Azure Database Administrator Associate", "DP-300", "I094-4717", "Dec 29, 2021"),
    (r"Azure IoT Developer Specialty", "---", "---", "2021"),
    (r"Azure AI Fundamentals", "AI-900", "---", "2021"),
    (r"Azure Data Fundamentals", "DP-900", "---", "2021"),
    (r"Azure Fundamentals", "AZ-900", "---", "2021"),
]

ONE_PAGE_BULLET_LIMITS = {
    "deloitte_us": 6,
    "zs": 3,
    "uci": 2,
    "deloitte_india": 5,
}


def _build_experience_section(archetype: str, one_page: bool = False) -> str:
    bullets = EXPERIENCE_BULLETS.get(archetype, EXPERIENCE_BULLETS["software_security"])
    if one_page:
        bullets = {
            k: v[:ONE_PAGE_BULLET_LIMITS.get(k, len(v))]
            for k, v in bullets.items()
        }
    us_title = DELOITTE_US_TITLE.get(archetype, "Engineering Manager")
    india_title = DELOITTE_INDIA_TITLE.get(archetype, "Cyber Security Solution Advisor")

    def _items(items: list[str]) -> str:
        return "\n            ".join(items)

    isep = "2pt" if one_page else "3pt"
    hgap = "2pt" if one_page else "3pt"

    return rf"""\section{{Experience}}

\begin{{tabularx}}{{\linewidth}}{{ @{{}}l r@{{}} }}
    \textbf{{Deloitte}} | {us_title} | \href{{https://www.deloitte.com/us/en/offices/us-locations/seattle.html}}{{Cloud Infra and Security Team | Seattle, WA}} & \hfill Jan 2025 - Present \\[{hgap}]
    \multicolumn{{2}}{{@{{}}X@{{}}}}{{\begin{{minipage}}[t]{{\linewidth}}
        \begin{{itemize}}[nosep,after=\strut, leftmargin=1em, itemsep={isep}]
            {_items(bullets["deloitte_us"])}
        \end{{itemize}}
    \end{{minipage}}}}
\end{{tabularx}}

\begin{{tabularx}}{{\linewidth}}{{ @{{}}l r@{{}} }}
    \textbf{{ZS Associates}} | Associate Consultant Intern | \href{{https://www.zs.com/}}{{Cloud and Big Data Team | Philadelphia, PA}} & \hfill Jun 2024 - Aug 2024 \\[{hgap}]
    \multicolumn{{2}}{{@{{}}X@{{}}}}{{\begin{{minipage}}[t]{{\linewidth}}
        \begin{{itemize}}[nosep,after=\strut, leftmargin=1em, itemsep={isep}]
            {_items(bullets["zs"])}
        \end{{itemize}}
    \end{{minipage}}}}
\end{{tabularx}}

\begin{{tabularx}}{{\linewidth}}{{ @{{}}l r@{{}} }}
    \textbf{{University of California, Irvine}} | Data \& Tech Fellow | \href{{https://odit.uci.edu/about/vc-profile.php}}{{Prof. Tom Andriola | Irvine, CA}} & \hfill Jan 2024 - Dec 2024 \\[{hgap}]
    \multicolumn{{2}}{{@{{}}X@{{}}}}{{\begin{{minipage}}[t]{{\linewidth}}
        \begin{{itemize}}[nosep,after=\strut, leftmargin=1em, itemsep={isep}]
            {_items(bullets["uci"])}
        \end{{itemize}}
    \end{{minipage}}}}
\end{{tabularx}}

\begin{{tabularx}}{{\linewidth}}{{ @{{}}l r@{{}} }}
    \textbf{{Deloitte}} | {india_title} | \href{{https://www.deloitte.com/ui/en}}{{Cloud Infrastructure Team | Gurugram, IN}} & \hfill Aug 2020 - Sep 2023 \\[{hgap}]
    \multicolumn{{2}}{{@{{}}X@{{}}}}{{\begin{{minipage}}[t]{{\linewidth}}
        \begin{{itemize}}[nosep,after=\strut, leftmargin=1em, itemsep={isep}]
            {_items(bullets["deloitte_india"])}
        \end{{itemize}}
    \end{{minipage}}}}
\end{{tabularx}} \\
"""


def _build_certs_section(archetype: str, one_page: bool = False) -> str:
    if one_page:
        certs = CERTS.get(archetype, CERTS["software_security"])[:3]
    else:
        archetype_certs = CERTS.get(archetype, CERTS["software_security"])
        archetype_exams = {c[1] for c in archetype_certs}
        remaining = [c for c in CERTS_ALL if c[1] not in archetype_exams]
        certs = archetype_certs + remaining
    items = []
    for name, exam, cred_id, date in certs:
        items.append(
            rf"            \item Microsoft Certified: \textbf{{{name}}} \hfill {exam} \hspace{{25mm}} \href{{https://github.com/stark3998/\#certifications}}{{{cred_id}}} \hspace{{20mm}} {date}"
        )
    items_str = "\n".join(items)
    cert_isep = "1.5pt" if one_page else "2.5pt"
    return rf"""\section{{Certifications \hfill \texorpdfstring{{\href{{https://github.com/stark3998/\#certifications}}{{\normalsize{{Link to all 11 Certifications}}}}}}{{}}}}
\begin{{tabularx}}{{\linewidth}}{{ @{{}}l r@{{}} }}
    \multicolumn{{2}}{{@{{}}X@{{}}}}{{\begin{{minipage}}[t]{{\linewidth}}
        \begin{{itemize}}[nosep,after=\strut, leftmargin=1em, itemsep={cert_isep}]
{items_str}
        \end{{itemize}}
    \end{{minipage}}}}
\end{{tabularx}}
\end{{document}}"""


ONE_PAGE_GEOMETRY = r"""
\geometry{scale=0.93, top=0.4cm, bottom=0.4cm}
\titlespacing{\section}{0pt}{2pt}{2pt}
\setlength{\parskip}{0pt}
"""

def _build_tex(archetype: str, one_page: bool = False) -> str:
    skills = SKILLS_TEMPLATES.get(archetype, SKILLS_TEMPLATES["software_security"])
    experience = _build_experience_section(archetype, one_page=one_page)
    certs = _build_certs_section(archetype, one_page=one_page)
    preamble = PREAMBLE
    if one_page:
        preamble = preamble.replace(
            r"\begin{document}",
            ONE_PAGE_GEOMETRY + r"\begin{document}",
        )
    return f"{preamble}\n{skills}\n{experience}\n{certs}\n"


def _build_cover_letter(
    company: str,
    title: str,
    archetype: str,
    location: str,
    analysis_content: str | None,
    matched_strong: str,
) -> str:
    archetype_display = ARCHETYPE_DISPLAY.get(archetype, archetype)
    strong_list = [re.sub(r"\s*\[.*?\]", "", s).strip() for s in matched_strong.split(";")] if matched_strong else []
    strong_list = [s for s in strong_list if s]
    top_matches = ", ".join(strong_list[:5]) if strong_list else "cloud security, Kubernetes, Terraform, Python, Azure"

    hook = f"I am writing to express my interest in the {title} role at {company}."
    if analysis_content:
        if "Multi-cloud" in analysis_content:
            hook += " My multi-cloud security engineering experience across Azure, AWS, and GCP aligns closely with the requirements outlined in this position."
        elif "Azure" in analysis_content:
            hook += " My deep Azure security engineering background, backed by 11 Microsoft certifications, maps directly to this role."
        else:
            hook += f" My experience in {archetype_display.lower()} aligns closely with the requirements of this position."

    evidence1 = (
        "As an Engineering Manager at Deloitte, I currently lead cloud infrastructure and security initiatives "
        "supporting 150K+ users across 5+ business units. I have architected and shipped production systems "
        "including an MCP server on AKS with OIDC-based workload identity and secrets management, hardened "
        "CI/CD pipelines against supply chain attacks across 2,000+ application deployments, and developed "
        "Python and PowerShell security tooling that reduced manual migration effort by 70%."
    )

    evidence2_options = {
        "cloud_security": (
            "Prior to my current role, I built an Automated Multi-Cloud Security Assessment Tool in Python "
            "that reduced manual effort by 78% and improved risk detection by 35%, and deployed fully automated "
            "Azure IaC solutions using Terraform across PaaS and IaaS environments. My 11 Microsoft certifications "
            "-- including Azure Security Engineer (AZ-500), Solutions Architect (AZ-304), and DevOps Engineer (AZ-400) "
            "-- reflect the breadth of my cloud security expertise."
        ),
        "security_architecture": (
            "I bring a strong consultative background from 3+ years as a Cyber Security Solution Advisor at Deloitte, "
            "where I architected Zero Trust security within Azure, conducted threat modeling and penetration testing "
            "of PaaS and Kubernetes environments, and designed reusable security reference architectures for enterprise "
            "adoption. My Master's in Computer Science from UC Irvine (4.0 GPA) complements this practical experience "
            "with strong analytical foundations."
        ),
        "software_security": (
            "Before this, I spent 3+ years as a Cyber Security Solution Advisor at Deloitte India, where I built "
            "an Automated Multi-Cloud Security Assessment Tool in Python, implemented Zero Trust network architecture, "
            "and developed an IaC scanning extension that pre-scanned Terraform templates for supply chain violations. "
            "My Master's in Computer Science from UC Irvine (4.0 GPA) and 11 Microsoft certifications round out "
            "my security engineering foundation."
        ),
        "cloud_devops": (
            "Previously, I designed and deployed fully automated Azure cloud solutions using Terraform IaC and "
            "Azure DevOps pipelines, overhauled ETL workflows converting 3,000 Parquet tables to Delta tables at "
            "ZS Associates (reducing cluster runtime by 14%), and engineered hybrid cloud infrastructure at UC Irvine. "
            "My 11 Microsoft certifications span architecture, DevOps, security, networking, and data engineering."
        ),
    }
    evidence2 = evidence2_options.get(archetype, evidence2_options["software_security"])

    why_company = (
        f"I am particularly drawn to {company} because of the opportunity to apply my {archetype_display.lower()} "
        f"skills at scale. I am confident that my combination of hands-on engineering, security architecture, "
        f"and cross-functional leadership experience would allow me to make an immediate impact on your team."
    )

    return f"""# Cover Letter — {title} at {company}

**Jatin Madan** | jatin.madan39@gmail.com | +1 (949) 213-9330 | Seattle, WA
LinkedIn: linkedin.com/in/jatin39 | GitHub: github.com/stark3998 | Portfolio: jatinmadan.com

---

**Date:** {datetime.now().strftime("%B %d, %Y")}

**Re:** {title} — {company} ({location})

---

{hook}

{evidence1}

{evidence2}

{why_company}

I would welcome the opportunity to discuss how my background in {top_matches} can contribute to {company}'s goals. Thank you for your consideration.

Best regards,
Jatin Madan

---

*Archetype: {archetype_display} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*
"""


def _compile_pdf(company_slug: str, resumes_dir: Path) -> str | None:
    import os
    tex_name = f"cv_{company_slug}.tex"
    pdf_candidate = resumes_dir / f"cv_{company_slug}.pdf"

    # Try local pdflatex first
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_name],
            cwd=str(resumes_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if pdf_candidate.exists():
            return f"Resumes/cv_{company_slug}.pdf"
    except FileNotFoundError:
        logger.info("pdflatex not found, trying Docker")
    except subprocess.TimeoutExpired:
        logger.warning("pdflatex timed out")

    # Fall back to Docker texlive
    try:
        host_path = str(resumes_dir.resolve()).replace("\\", "/")
        logger.info(f"Docker compile: volume={host_path}:/work, tex={tex_name}")
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{host_path}:/work",
                "-w", "/work",
                "texlive/texlive:latest",
                "pdflatex", "-interaction=nonstopmode", tex_name,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        )
        logger.info(f"Docker returncode={result.returncode}, pdf_exists={pdf_candidate.exists()}")
        if result.returncode != 0:
            logger.warning(f"Docker stderr: {result.stderr[-300:]}")
        if pdf_candidate.exists():
            return f"Resumes/cv_{company_slug}.pdf"
    except FileNotFoundError as e:
        logger.warning(f"Docker not found: {e}")
    except subprocess.TimeoutExpired:
        logger.warning("Docker timed out")
    except Exception as e:
        logger.warning(f"Docker compile error: {e}")

    return None


def _validate_against_jd(tex_content: str, analysis_content: str | None) -> dict | None:
    """Check how well the generated resume covers the JD's required keywords."""
    if not analysis_content:
        return None

    keywords = set()

    for match in re.finditer(r'\d+\.\s+\*\*(.+?)\*\*\s+\(mentioned', analysis_content):
        keywords.add(match.group(1).strip().lower())

    for match in re.finditer(r'\|\s*(?:Cloud|Security|DevOps/IaC|Monitoring|Languages|Data|Frameworks)\s*\|\s*(.+?)\s*\|', analysis_content):
        for tool in match.group(1).split(","):
            clean = tool.strip().lower()
            if clean and len(clean) >= 2:
                keywords.add(clean)

    if not keywords:
        return None

    tex_lower = tex_content.lower()
    matched = []
    missing = []
    for kw in keywords:
        if len(kw) < 3:
            found = bool(re.search(r'\b' + re.escape(kw) + r'\b', tex_lower))
        else:
            found = kw in tex_lower
        if found:
            matched.append(kw)
        else:
            missing.append(kw)

    return {
        "matched_keywords": sorted(matched),
        "missing_keywords": sorted(missing),
        "coverage_percent": round(len(matched) / len(keywords) * 100, 1) if keywords else 0,
        "total_keywords": len(keywords),
    }


# ---------------------------------------------------------------------------
# Endpoint: generate tailored resume + cover letter
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=ResumeResponse)
def generate_resume(request: ResumeRequest):
    latest = _find_latest_csv(FILTERED_DIR, "filtered_")
    if not latest:
        raise HTTPException(status_code=404, detail="No filtered jobs found")

    df = pd.read_csv(latest)
    df = df.reset_index(drop=True)

    if request.job_id >= len(df):
        raise HTTPException(status_code=404, detail="Job not found")

    row = df.iloc[request.job_id]
    company = str(row.get("company", "Unknown"))
    title = str(row.get("title", "Unknown"))
    company_slug = _slugify(company)
    title_slug = _slugify(title)

    archetype = request.archetype_override or str(row.get("search_archetype", "software_security"))
    if archetype not in SKILLS_TEMPLATES:
        archetype = "software_security"

    city = str(row.get("city", "")) if pd.notna(row.get("city")) else ""
    state = str(row.get("state", "")) if pd.notna(row.get("state")) else ""
    location = ", ".join(filter(None, [city, state])) or "Not specified"
    matched_strong = str(row.get("matched_strong", "")) if pd.notna(row.get("matched_strong")) else ""

    # Find analysis
    analysis_content = None
    analysis_file = None
    candidate = ANALYSIS_DIR / f"{company_slug}_{title_slug}.md"
    if candidate.exists():
        analysis_file = candidate.name
        analysis_content = candidate.read_text(encoding="utf-8")
    else:
        for f in ANALYSIS_DIR.glob(f"{company_slug}_*.md"):
            analysis_file = f.name
            analysis_content = f.read_text(encoding="utf-8")
            break

    # Archive existing resumes/cover letters before generating new ones
    _migrate_flat_archive()
    _archive_existing()

    # Generate tailored .tex
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    tex_content = _build_tex(archetype, one_page=request.one_page)
    tex_path = RESUMES_DIR / f"cv_{company_slug}.tex"
    tex_path.write_text(tex_content, encoding="utf-8")

    # Generate cover letter
    COVER_LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    cl_content = _build_cover_letter(company, title, archetype, location, analysis_content, matched_strong)
    cl_path = COVER_LETTERS_DIR / f"coverletter_{company_slug}.md"
    cl_path.write_text(cl_content, encoding="utf-8")

    # Compile PDF — try pdflatex, fall back to Docker texlive
    citations = RESUMES_DIR / "citations.bib"
    if not citations.exists():
        citations.touch()

    pdf_path_str = _compile_pdf(company_slug, RESUMES_DIR)

    # Clean LaTeX build artifacts
    for ext in ("aux", "log", "out", "bbl", "bcf", "blg", "run.xml", "fdb_latexmk", "fls", "synctex.gz"):
        artifact = RESUMES_DIR / f"cv_{company_slug}.{ext}"
        if artifact.exists():
            artifact.unlink()

    # Validate resume against JD keywords
    validation = _validate_against_jd(tex_content, analysis_content)

    page_label = "1-page" if request.one_page else "2-page"
    return ResumeResponse(
        success=True,
        tex_path=f"Resumes/cv_{company_slug}.tex",
        pdf_path=pdf_path_str,
        cover_letter_path=f"CoverLetters/coverletter_{company_slug}.md",
        analysis_path=f"pipeline_output/analyses/{analysis_file}" if analysis_file else None,
        message=f"Generated {page_label} tailored resume ({ARCHETYPE_DISPLAY.get(archetype, archetype)}) and cover letter for {title} at {company}."
        + (" PDF compiled." if pdf_path_str else " PDF compilation unavailable (install pdflatex or Docker)."),
        validation=validation,
    )


@router.get("/list")
def list_resumes():
    resumes = []
    if RESUMES_DIR.exists():
        for f in sorted(RESUMES_DIR.glob("cv_*.tex"), key=lambda x: x.stat().st_mtime, reverse=True):
            company_slug = f.stem.replace("cv_", "")
            cl_exists = (COVER_LETTERS_DIR / f"coverletter_{company_slug}.md").exists() if COVER_LETTERS_DIR.exists() else False
            resumes.append({
                "name": company_slug,
                "tex": f.name,
                "has_pdf": (RESUMES_DIR / f"{f.stem}.pdf").exists(),
                "has_cover_letter": cl_exists,
                "cover_letter": f"coverletter_{company_slug}.md" if cl_exists else None,
                "modified": f.stat().st_mtime,
                "archived": False,
            })

    archive_base = RESUMES_DIR / "archive"
    if archive_base.exists():
        for company_dir in sorted(archive_base.iterdir(), reverse=True):
            if not company_dir.is_dir():
                continue
            for tex_file in sorted(company_dir.glob("cv_*.tex"), key=lambda x: x.stat().st_mtime, reverse=True):
                slug = tex_file.stem.replace("cv_", "")
                pdf_exists = (company_dir / f"{tex_file.stem}.pdf").exists()
                cl_file = company_dir / f"coverletter_{slug}.md"
                resumes.append({
                    "name": slug,
                    "tex": tex_file.name,
                    "has_pdf": pdf_exists,
                    "has_cover_letter": cl_file.exists(),
                    "cover_letter": f"coverletter_{slug}.md" if cl_file.exists() else None,
                    "modified": tex_file.stat().st_mtime,
                    "archived": True,
                    "archive_path": str(company_dir.relative_to(RESUMES_DIR)),
                })
    return resumes


@router.get("/analysis/{filename}")
def get_analysis(filename: str):
    safe_name = Path(filename).name
    filepath = ANALYSIS_DIR / safe_name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Analysis file not found")
    return {"content": filepath.read_text(encoding="utf-8")}


@router.get("/preview/{filename}")
def preview_pdf(filename: str):
    safe_name = Path(filename).name
    if not safe_name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF preview supported")
    filepath = RESUMES_DIR / safe_name
    if not filepath.exists():
        archive_base = RESUMES_DIR / "archive"
        if archive_base.exists():
            for candidate in archive_base.rglob(safe_name):
                filepath = candidate
                break
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        filepath,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={safe_name}"},
    )


@router.get("/download/{filename}")
def download_file(filename: str):
    safe_name = Path(filename).name
    for directory in [RESUMES_DIR, ANALYSIS_DIR, COVER_LETTERS_DIR]:
        filepath = directory / safe_name
        if filepath.exists():
            return FileResponse(filepath, filename=safe_name)
    archive_base = RESUMES_DIR / "archive"
    if archive_base.exists():
        for candidate in archive_base.rglob(safe_name):
            return FileResponse(candidate, filename=safe_name)
    raise HTTPException(status_code=404, detail="File not found")

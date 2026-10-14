terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.6" }
  }
}

provider "docker" {
  host = var.docker_host
}

variable "docker_host" {
  description = "Windows Docker Desktop: npipe:////./pipe/docker_engine; Linux: unix:///var/run/docker.sock"
  type        = string
  default     = "npipe:////./pipe/docker_engine"
}

variable "image_id" {
  description = "Immutable local workload image ID obtained from docker image inspect. Build workload first."
  type        = string
  validation {
    condition     = can(regex("^sha256:[a-f0-9]{64}$", var.image_id))
    error_message = "Pass an immutable sha256 image ID."
  }
}

variable "port" {
  type    = number
  default = 8099
  validation {
    condition     = var.port >= 1024 && var.port <= 65535 && floor(var.port) == var.port
    error_message = "Use an unprivileged TCP port."
  }
}

resource "docker_container" "golden_workload" {
  name          = "launchpad-terraform-golden-workload"
  image         = var.image_id
  memory        = 64
  memory_swap   = 128
  cpu_shares    = 256
  read_only     = true
  user          = "10001:10001"
  env           = ["APP_VERSION=v1"]
  security_opts = ["no-new-privileges"]
  capabilities { drop = ["ALL"] }
  ports {
    internal = 8000
    external = var.port
    ip       = "127.0.0.1"
  }
  labels {
    label = "dev.launchpad.namespace"
    value = "launchpad-terraform"
  }
}

output "health_url" {
  value = "http://127.0.0.1:${var.port}/health"
}

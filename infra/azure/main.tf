terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.62" }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" { type = string }
variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{5,30}$", var.name))
    error_message = "Use a globally unique lowercase name, 6-31 characters."
  }
}
variable "location" {
  type    = string
  default = "centralindia"
}
variable "image" {
  description = "Published workload image, including registry and immutable digest. No control-plane Docker access is provided by App Service."
  type        = string
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Reference a published immutable digest."
  }
}
variable "registry_url" {
  type = string
}

resource "azurerm_resource_group" "workload" {
  name     = "${var.name}-rg"
  location = var.location
  tags     = { project = "launchpad", managed_by = "terraform" }
}

resource "azurerm_service_plan" "workload" {
  name                = "${var.name}-plan"
  resource_group_name = azurerm_resource_group.workload.name
  location            = azurerm_resource_group.workload.location
  os_type             = "Linux"
  sku_name            = "B1"
}

resource "azurerm_linux_web_app" "workload" {
  name                          = var.name
  resource_group_name           = azurerm_resource_group.workload.name
  location                      = azurerm_resource_group.workload.location
  service_plan_id               = azurerm_service_plan.workload.id
  https_only                    = true
  public_network_access_enabled = true
  identity { type = "SystemAssigned" }
  site_config {
    minimum_tls_version = "1.2"
    always_on           = true
    health_check_path   = "/health"
    application_stack {
      docker_image_name   = var.image
      docker_registry_url = var.registry_url
    }
  }
  app_settings = {
    WEBSITES_PORT = "8000"
    APP_VERSION   = "v1"
  }
}

output "workload_url" {
  value = "https://${azurerm_linux_web_app.workload.default_hostname}"
}

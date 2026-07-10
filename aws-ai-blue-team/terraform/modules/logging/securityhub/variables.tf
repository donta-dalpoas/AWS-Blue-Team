variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "enable_cis_standard" {
  description = "Whether to enable CIS AWS Foundations Benchmark"
  type        = bool
  default     = true
}

variable "enable_pci_standard" {
  description = "Whether to enable PCI DSS standard"
  type        = bool
  default     = false
}

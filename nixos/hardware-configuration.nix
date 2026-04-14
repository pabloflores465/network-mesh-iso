# Generic x86_64 hardware configuration for USB-boot nodes
{ config, lib, pkgs, modulesPath, ... }:

{
  imports = [ (modulesPath + "/installer/scan/not-detected.nix") ];

  boot.initrd.availableKernelModules = [ "xhci_pci" "ehci_pci" "ahci" "usbhid" "sd_mod" "sr_mod" ];
  boot.initrd.kernelModules = [ ];
  boot.kernelModules = [ "kvm-amd" "kvm-intel" ];
  boot.extraModulePackages = [ ];

  # No swap for USB live
  swapDevices = [ ];

  # Use USB stick as root
  fileSystems."/" = {
    device = "/dev/disk/by-label/NIXOS_ISO";
    fsType = "iso9660";
  };

  # Use tmpfs for writable areas (USB is often read-only or slow)
  fileSystems."/var/lib/mesh" = {
    device = "tmpfs";
    fsType = "tmpfs";
    options = [ "size=512M" "mode=0777" ];
  };

  fileSystems."/tmp" = {
    device = "tmpfs";
    fsType = "tmpfs";
    options = [ "size=1G" "mode=1777" ];
  };

  # Use less generic options for USB boot
  boot.kernelParams = [ "quiet" "loglevel=3" ];
}

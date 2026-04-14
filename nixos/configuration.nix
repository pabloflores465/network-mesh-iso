{ config, pkgs, lib, mesh-scripts, ... }:

{
  nixpkgs.config.allowUnfree = true;

  networking.hostName = "mesh-node";

  # WiFi managed by our scripts (wpa_supplicant + hostapd)
  networking.wireless.enable = false;
  networking.wireless.iwd.enable = false;
  networking.useNetworkd = true;

  # Firewall
  networking.firewall.allowedTCPPorts = [ 22 8000 8001 8080 ];
  networking.firewall.allowedUDPPorts = [ 5353 8001 ];

  time.timeZone = "America/Mexico_City";
  i18n.defaultLocale = "es_MX.UTF-8";

  services.openssh.enable = true;

  services.avahi = {
    enable = true;
    nssmdns4 = true;
    publish = { enable = true; userServices = true; addresses = true; };
  };

  environment.systemPackages = with pkgs; [
    python311
    python311Packages.flask
    python311Packages.requests
    python311Packages.psutil
    wget curl jq
    hostapd wpa_supplicant wireless-regdb iperf3 dnsmasq
    icecast ffmpeg-full mpg123 alsa-utils darkice
    screen tmux htop vim tree sqlite netcat-openbsd dnsutils lshw procps mtr ethtool
    mesh-scripts
  ];

  systemd.services.mesh-setup = {
    description = "Setup Mesh Music Node Environment";
    wantedBy = [ "multi-user.target" ];
    script = ''
      mkdir -p /opt/mesh/songs/local /opt/mesh/songs/nodes /var/lib/mesh
      MAC=$(ip link | awk '/ether/{print $2; exit}' || echo "00000000")
      NODE_ID=$(echo "$MAC" | md5sum | cut -c1-8)
      echo "$NODE_ID" > /opt/mesh/node_id
      hostname "mesh-$NODE_ID"
      echo "Mesh node initialized: $NODE_ID"
    '';
    serviceConfig.Type = "oneshot";
  };

  systemd.services.mesh-agent = {
    description = "Network Music Mesh - Node Agent";
    wantedBy = [ "multi-user.target" ];
    after = [ "mesh-setup.service" ];
    serviceConfig = {
      ExecStart = "${pkgs.python311}/bin/python ${mesh-scripts}/bin/mesh_agent.py";
      Restart = "always";
      RestartSec = 5;
      WorkingDirectory = "/var/lib/mesh";
    };
  };

  systemd.services.mesh-webui = {
    description = "Mesh Music Node Web Dashboard";
    wantedBy = [ "multi-user.target" ];
    after = [ "mesh-agent.service" ];
    serviceConfig = {
      ExecStart = "${pkgs.python311}/bin/python ${mesh-scripts}/bin/webui.py";
      Restart = "always";
      RestartSec = 3;
      WorkingDirectory = "/var/lib/mesh";
    };
  };

  services.getty.autologinUser = lib.mkForce "root";

  services.getty.helpLine = lib.mkForce ''
    Mesh Music Node - TUI: mesh_tui.py | Web: http://<ip>:8080
  '';

  system.stateVersion = "24.11";
}

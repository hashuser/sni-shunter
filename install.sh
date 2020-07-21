#!/bin/bash
create_service(){
  touch $(cd "$(dirname "$0")";pwd)/SNI.service
  cat>$(cd "$(dirname "$0")";pwd)/SNI.service<<EOF
  [Unit]
  Description=SNI Network Service
  After=rc-local.service

  [Service]
  Type=simple
  User=root
  Group=root
  WorkingDirectory=$(cd "$(dirname "$0")";pwd)
  ExecStart=/usr/bin/python3.8 $(cd "$(dirname "$0")";pwd)/server.py
  LimitNOFILE=1048575
  Restart=always
  TasksMax=infinity

  [Install]
  WantedBy=multi-user.target
EOF
}

install_service(){
  echo "root  soft nofile 1048575" >> /etc/security/limits.conf
  echo "root  hard nofile 1048575" >> /etc/security/limits.conf
  mv $(cd "$(dirname "$0")";pwd)/SNI.service /etc/systemd/system/
  systemctl enable SNI.service
  systemctl start SNI.service
}

create_shortcut(){
  echo "alias SNI_config='vim $(cd "$(dirname "$0")";pwd)/config.json'">>~/.bashrc
  echo "alias SNI_uninstall='rm -r $(cd "$(dirname "$0")";pwd)'">>~/.bashrc
  reboot
}

automatic_reboot(){
  apt-get install cron -y
  echo "0 16 * * * root systemctl restart SNI" >> /etc/crontab
  echo "0 16 * * 7 root reboot" >> /etc/crontab
  service cron restart
}

install_SNI(){
  mkdir $(cd "$(dirname "$0")";pwd)/SNI-shunter
  cd $(cd "$(dirname "$0")";pwd)/SNI-shunter
  apt-get update
  dpkg-reconfigure libc6
  DEBIAN_FRONTEND=noninteractive dpkg --configure libssl1.1 
  DEBIAN_FRONTEND=noninteractive apt-get install -y libssl1.1
  apt-get install python3.8 -y
  wget -O server.py https://raw.githubusercontent.com/hashuser/sni-shunter/master/server.py
}

main(){
  install_SNI
  create_service
  install_service
  automatic_reboot
  create_shortcut
}

main

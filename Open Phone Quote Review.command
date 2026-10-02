#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
review_interface=$(/sbin/route -n get default | /usr/bin/awk '/interface:/{print $2}')
review_address=$(/usr/sbin/ipconfig getifaddr "$review_interface")
if [[ -z "$review_address" ]]; then
  print 'Connect your Mac to your home network, then try again.'
  read
  exit 1
fi
print 'Keep this window open. Use the phone address and pairing code printed below.'
python3 scripts/review_server.py --lan-ip "$review_address"

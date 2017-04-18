## Receive alerts on Zabbix unsupported items and unknown triggers (pre Zabbix 2.2)
====================

This script and template allow to receive detailed notifications about items in unsupported state and triggers in unknown state in Zabbix.

This is only needed for Zabbix up to 2.0. Zabbix 2.2 includes similar functionality in core: https://www.zabbix.com/documentation/2.2/manual/config/notifications/unsupported_item

Tested and works on Zabbix 2.0, Postgresql 9.2. Will not work on Mysql without hacking.

### Installation

1. Create zabbix-api user in Zabbix web interface
2. Put the script in /etc/zabbix/externalscripts
3. Edit the variables in the scirpt to match your environment. This includes web and db access. Test that script executes properly under zabbix account.
4. Import the template, assign in to your Zabbix server host.


### Example notification
(You have to include item.lastvalue in alert body, as desribed later)

```
Zabbix triggers in unknown state found: PROBLEM
Last value: Triggers in unknown state found:
1) hostname: host1.domain.tld, host ip: 127.0.0.1, trigger name: Puppetd last report is too old on server {HOSTNAME}
2) hostname: host1.domain.tld, host ip: 127.0.0.1, trigger name: Puppetd is administratively disabled on {HOSTNAME}
3) hostname: host1.domain.tld, host ip: 127.0.0.1, trigger name: Puppet cert is revoked on {HOSTNAME}
4) hostname: host1.domain.tld, host ip: 127.0.0.1, trigger name: Puppetd events failure on server {HOSTNAME}

Event ID: 3158053
```

Sample alert action message body to achieve the above:
```
{TRIGGER.NAME}: {STATUS}
Last value: {ITEM.LASTVALUE}
Event ID: {EVENT.ID}
```

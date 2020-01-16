from ipam.constants import *
from ipam.models import IPAddress, Prefix, VRF, VLAN
from extras.reports import Report

LOOPBACK_ROLES = [
    IPADDRESS_ROLE_LOOPBACK,
    IPADDRESS_ROLE_ANYCAST,
    IPADDRESS_ROLE_VIP,
    IPADDRESS_ROLE_VRRP,
]

# CheckPrefixLength forked from https://gist.github.com/candlerb/5380a7cdd03b60fbd02a664feb266d44
class CheckPrefixLength(Report):
    description = "Check each IP address has the prefix length of the enclosing subnet"

    def test_prefix_lengths(self):
        prefixes = list(Prefix.objects.all())
        prefixes.sort(key=lambda k: k.prefix)   # overlapping subnets sort in order from largest to smallest
        for ipaddr in IPAddress.objects.all():
            a = ipaddr.address
            if str(a).startswith("fe80"):
                self.log_success(ipaddr)
                continue
            if ipaddr.family != a.version:
                self.log_failure(ipaddr, "family (%d) inconsistent with address.version (%d)" %
                                 (ipaddr.family, a.version))
                continue
            # We allow loopback-like things to be single address *or* have the parent prefix length
            if ipaddr.role in LOOPBACK_ROLES and (
                     (a.version == 4 and a.prefixlen == 32) or
                     (a.version == 6 and a.prefixlen == 128)):
                self.log_success(ipaddr)
                continue
            parents = [p for p in prefixes if
                              (p.vrf and p.vrf.id) == (ipaddr.vrf and ipaddr.vrf.id) and
                               p.prefix.version == a.version and a.ip in p.prefix]
            if not parents:
                self.log_info(ipaddr, "No parent prefix")
                continue
            parent = parents[-1]
            if a.prefixlen != parent.prefix.prefixlen:
                self.log_failure(ipaddr, "prefixlen (%d) inconsistent with parent prefix (%s)" %
                                 (a.prefixlen, str(parent.prefix)))
                continue
            # if the parent prefix also contains child prefixes, that probably means that
            # an intermediate parent prefix is missing
            pchildren = [p for p in prefixes if
                                (p.vrf and p.vrf.id) == (parent.vrf and parent.vrf.id) and
                                 p.prefix.version == parent.prefix.version and
                                 p.prefix != parent.prefix and
                                 p.prefix in parent.prefix]
            if pchildren:
                self.log_warning(ipaddr, "parent prefix (%s) contains %d other child prefix(es)" %
                                 (str(parent.prefix), len(pchildren)))
                continue
            self.log_success(ipaddr)

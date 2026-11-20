"""Static choice lists for registration. Plain text only (no flag emoji)."""

from django.utils.translation import gettext_lazy as _

# (dial code, label). Same 21 countries as the original portal, Thailand first.
# The code leads the label so it stays visible when the select is narrow.
COUNTRY_DIAL_CODES = [
    ("+66", _("+66 Thailand")),
    ("+1", _("+1 United States / Canada")),
    ("+44", _("+44 United Kingdom")),
    ("+61", _("+61 Australia")),
    ("+81", _("+81 Japan")),
    ("+82", _("+82 South Korea")),
    ("+86", _("+86 China")),
    ("+852", _("+852 Hong Kong")),
    ("+886", _("+886 Taiwan")),
    ("+65", _("+65 Singapore")),
    ("+60", _("+60 Malaysia")),
    ("+62", _("+62 Indonesia")),
    ("+63", _("+63 Philippines")),
    ("+84", _("+84 Vietnam")),
    ("+91", _("+91 India")),
    ("+49", _("+49 Germany")),
    ("+33", _("+33 France")),
    ("+31", _("+31 Netherlands")),
    ("+46", _("+46 Sweden")),
    ("+7", _("+7 Russia")),
    ("+971", _("+971 United Arab Emirates")),
]

NATIONALITIES = [
    ("TH", _("Thai")),
    ("US", _("American")),
    ("CA", _("Canadian")),
    ("GB", _("British")),
    ("AU", _("Australian")),
    ("JP", _("Japanese")),
    ("KR", _("Korean")),
    ("CN", _("Chinese")),
    ("HK", _("Hong Konger")),
    ("TW", _("Taiwanese")),
    ("SG", _("Singaporean")),
    ("MY", _("Malaysian")),
    ("ID", _("Indonesian")),
    ("PH", _("Filipino")),
    ("VN", _("Vietnamese")),
    ("IN", _("Indian")),
    ("DE", _("German")),
    ("FR", _("French")),
    ("NL", _("Dutch")),
    ("SE", _("Swedish")),
    ("RU", _("Russian")),
    ("AE", _("Emirati")),
    ("XX", _("Other")),
]

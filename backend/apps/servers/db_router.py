# ফাইল: backend/apps/servers/db_router.py
# এই ফাইলটি FreeRADIUS models-কে 'radius' database-এ route করে।
# Django-র multiple database support ব্যবহার করে।

# FreeRADIUS-এর সব models এই app-এ আছে
RADIUS_MODELS = {'radcheck', 'radreply', 'radusergroup', 'radgroupcheck', 'radgroupreply', 'radacct'}


class RadiusDBRouter:
    """
    FreeRADIUS models-কে 'radius' database-এ এবং
    বাকি সব models-কে 'default' database-এ route করে।
    """

    def db_for_read(self, model, **hints):
        """Read operation কোন database-এ হবে।"""
        if model._meta.db_table in RADIUS_MODELS:
            return 'radius'
        return 'default'

    def db_for_write(self, model, **hints):
        """Write operation কোন database-এ হবে।"""
        if model._meta.db_table in RADIUS_MODELS:
            return 'radius'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """দুটো object-এর মধ্যে relation allow করা হবে কিনা।"""
        # একই database-এর মধ্যে relation allow
        radius_tables = RADIUS_MODELS
        obj1_is_radius = obj1._meta.db_table in radius_tables
        obj2_is_radius = obj2._meta.db_table in radius_tables

        if obj1_is_radius == obj2_is_radius:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Migration কোন database-এ চলবে।"""
        if model_name and model_name.lower() in RADIUS_MODELS:
            # FreeRADIUS tables 'radius' database-এ migrate হবে
            return db == 'radius'
        # বাকি সব 'default' database-এ migrate হবে
        if db == 'radius':
            return False
        return True

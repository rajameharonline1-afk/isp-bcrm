-- ফাইল: backend/scripts/freeradius/sql_schema.sql
-- এই ফাইলটি FreeRADIUS-এর জন্য PostgreSQL database schema তৈরি করে।
-- FreeRADIUS server-এ rlm_sql module-এর জন্য প্রয়োজনীয় সব table।

-- Database তৈরি করা (যদি না থাকে)
-- CREATE DATABASE radius;
-- \c radius;

-- =============================================
-- radcheck - User authentication এবং authorization check
-- =============================================
CREATE TABLE IF NOT EXISTS radcheck (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          VARCHAR(2)  NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS radcheck_username ON radcheck (username, attribute);

-- =============================================
-- radreply - Authentication সফল হলে reply attributes
-- =============================================
CREATE TABLE IF NOT EXISTS radreply (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          VARCHAR(2)  NOT NULL DEFAULT '=',
    value       VARCHAR(253) NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS radreply_username ON radreply (username, attribute);

-- =============================================
-- radusergroup - User কোন group (package)-এ আছে
-- =============================================
CREATE TABLE IF NOT EXISTS radusergroup (
    username    VARCHAR(64) NOT NULL DEFAULT '',
    groupname   VARCHAR(64) NOT NULL DEFAULT '',
    priority    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (username, groupname)
);
CREATE INDEX IF NOT EXISTS radusergroup_username ON radusergroup (username);

-- =============================================
-- radgroupcheck - Group-level check attributes
-- =============================================
CREATE TABLE IF NOT EXISTS radgroupcheck (
    id          SERIAL PRIMARY KEY,
    groupname   VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          VARCHAR(2)  NOT NULL DEFAULT ':=',
    value       VARCHAR(253) NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radgroupcheck_groupname ON radgroupcheck (groupname, attribute);

-- =============================================
-- radgroupreply - Group-level reply attributes (Rate-Limit, etc.)
-- =============================================
CREATE TABLE IF NOT EXISTS radgroupreply (
    id          SERIAL PRIMARY KEY,
    groupname   VARCHAR(64) NOT NULL DEFAULT '',
    attribute   VARCHAR(64) NOT NULL DEFAULT '',
    op          VARCHAR(2)  NOT NULL DEFAULT '=',
    value       VARCHAR(253) NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radgroupreply_groupname ON radgroupreply (groupname, attribute);

-- =============================================
-- radacct - Accounting/Session records
-- =============================================
CREATE TABLE IF NOT EXISTS radacct (
    radacctid           BIGSERIAL PRIMARY KEY,
    acctsessionid       VARCHAR(64) NOT NULL DEFAULT '',
    acctuniqueid        VARCHAR(32) NOT NULL DEFAULT '',
    username            VARCHAR(64) NOT NULL DEFAULT '',
    realm               VARCHAR(64) DEFAULT '',
    nasipaddress        INET NOT NULL,
    nasidentifier       VARCHAR(64) DEFAULT '',
    nasportid           VARCHAR(15) DEFAULT '',
    nasporttype         VARCHAR(32) DEFAULT '',
    acctstarttime       TIMESTAMP WITH TIME ZONE,
    acctupdatetime      TIMESTAMP WITH TIME ZONE,
    acctstoptime        TIMESTAMP WITH TIME ZONE,
    acctinterval        BIGINT,
    acctsessiontime     BIGINT DEFAULT 0,
    acctauthentic       VARCHAR(32) DEFAULT '',
    connectinfo_start   TEXT DEFAULT '',
    connectinfo_stop    TEXT DEFAULT '',
    acctinputoctets     BIGINT DEFAULT 0,
    acctoutputoctets    BIGINT DEFAULT 0,
    calledstationid     VARCHAR(50) DEFAULT '',
    callingstationid    VARCHAR(50) DEFAULT '',
    acctterminatecause  VARCHAR(32) DEFAULT '',
    servicetype         VARCHAR(32) DEFAULT '',
    framedprotocol      VARCHAR(32) DEFAULT '',
    framedipaddress     INET,
    CONSTRAINT acctuniqueid_unique UNIQUE (acctuniqueid)
);
CREATE INDEX IF NOT EXISTS radacct_username ON radacct (username);
CREATE INDEX IF NOT EXISTS radacct_nasipaddress ON radacct (nasipaddress);
CREATE INDEX IF NOT EXISTS radacct_acctsessionid ON radacct (acctsessionid);
CREATE INDEX IF NOT EXISTS radacct_acctstarttime ON radacct (acctstarttime);
CREATE INDEX IF NOT EXISTS radacct_framedipaddress ON radacct (framedipaddress);

-- =============================================
-- Example: ISP Package Group তৈরি (10Mbps)
-- =============================================
-- INSERT INTO radgroupreply (groupname, attribute, op, value)
-- VALUES ('10Mbps', 'Mikrotik-Rate-Limit', '=', '10M/10M');

-- INSERT INTO radgroupreply (groupname, attribute, op, value)
-- VALUES ('20Mbps', 'Mikrotik-Rate-Limit', '=', '20M/20M');

-- =============================================
-- FreeRADIUS User তৈরির উদাহরণ
-- =============================================
-- INSERT INTO radcheck (username, attribute, op, value)
-- VALUES ('testuser', 'Cleartext-Password', ':=', 'testpass');

-- INSERT INTO radusergroup (username, groupname, priority)
-- VALUES ('testuser', '10Mbps', 1);

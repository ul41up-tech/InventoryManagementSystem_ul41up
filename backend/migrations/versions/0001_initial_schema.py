"""initial schema

由 tools/generate_initial_migration.py 產生（SQLAlchemy metadata → PostgreSQL DDL）。
對應 PRD addendum §1.4 的資料模型。

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
        op.execute(sa.text('CREATE TABLE customers (\n\tid SERIAL NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tcontact VARCHAR(100), \n\tphone VARCHAR(50), \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (name)\n);'))
        op.execute(sa.text('CREATE TABLE items (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(20) NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tunit VARCHAR(20) NOT NULL, \n\tsuggested_price NUMERIC(12, 2), \n\ttarget_margin_rate NUMERIC(6, 4), \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code)\n);'))
        op.execute(sa.text('CREATE INDEX ix_items_name ON items (name);'))
        op.execute(sa.text('CREATE TABLE suppliers (\n\tid SERIAL NOT NULL, \n\ttax_id VARCHAR(20) NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tcontact VARCHAR(100), \n\tphone VARCHAR(50), \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tax_id)\n);'))
        op.execute(sa.text('CREATE TABLE users (\n\tid SERIAL NOT NULL, \n\tusername VARCHAR(50) NOT NULL, \n\tpassword_hash VARCHAR(255) NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\trole VARCHAR(20) NOT NULL, \n\tis_active BOOLEAN NOT NULL, \n\tmust_change_password BOOLEAN NOT NULL, \n\tfailed_attempts INTEGER NOT NULL, \n\tlocked_until TIMESTAMP WITHOUT TIME ZONE, \n\tlast_login_at TIMESTAMP WITHOUT TIME ZONE, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (username)\n);'))
        op.execute(sa.text('CREATE TABLE warehouses (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(20) NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tis_virtual BOOLEAN NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code)\n);'))
        op.execute(sa.text('CREATE TABLE grn (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tsupplier_id INTEGER, \n\toperator_id INTEGER NOT NULL, \n\tin_date DATE NOT NULL, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(supplier_id) REFERENCES suppliers (id), \n\tFOREIGN KEY(operator_id) REFERENCES users (id)\n);'))
        op.execute(sa.text('CREATE TABLE item_suppliers (\n\tid SERIAL NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tsupplier_id INTEGER NOT NULL, \n\tis_primary BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_item_supplier UNIQUE (item_id, supplier_id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(supplier_id) REFERENCES suppliers (id)\n);'))
        op.execute(sa.text('CREATE TABLE locations (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\twarehouse_id INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_location_code_per_warehouse UNIQUE (code, warehouse_id), \n\tFOREIGN KEY(warehouse_id) REFERENCES warehouses (id)\n);'))
        op.execute(sa.text('CREATE TABLE purchase_orders (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tsupplier_id INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\torder_date DATE NOT NULL, \n\texpected_date DATE, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(supplier_id) REFERENCES suppliers (id)\n);'))
        op.execute(sa.text('CREATE TABLE reorder_points (\n\tid SERIAL NOT NULL, \n\titem_id INTEGER NOT NULL, \n\twarehouse_id INTEGER NOT NULL, \n\treorder_point NUMERIC(14, 3) NOT NULL, \n\tlead_time_days INTEGER, \n\tmin_order_qty NUMERIC(14, 3), \n\tpack_multiple NUMERIC(14, 3), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_reorder_item_warehouse UNIQUE (item_id, warehouse_id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(warehouse_id) REFERENCES warehouses (id)\n);'))
        op.execute(sa.text('CREATE TABLE sales_orders (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tcustomer_id INTEGER NOT NULL, \n\tsalesperson_id INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\torder_date DATE NOT NULL, \n\tdiscount_type VARCHAR(20) NOT NULL, \n\tdiscount_value NUMERIC(14, 2) NOT NULL, \n\ttotal_amount NUMERIC(14, 2) NOT NULL, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(customer_id) REFERENCES customers (id), \n\tFOREIGN KEY(salesperson_id) REFERENCES users (id)\n);'))
        op.execute(sa.text('CREATE TABLE shipping_orders (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tcustomer_id INTEGER NOT NULL, \n\toperator_id INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tship_date DATE, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(customer_id) REFERENCES customers (id), \n\tFOREIGN KEY(operator_id) REFERENCES users (id)\n);'))
        op.execute(sa.text('CREATE TABLE stock_adjustments (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tadjust_type VARCHAR(20) NOT NULL, \n\treason VARCHAR(100) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\toperator_id INTEGER NOT NULL, \n\tapproved_by INTEGER, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(operator_id) REFERENCES users (id), \n\tFOREIGN KEY(approved_by) REFERENCES users (id)\n);'))
        op.execute(sa.text('CREATE TABLE transfer_orders (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tfrom_warehouse_id INTEGER NOT NULL, \n\tto_warehouse_id INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tship_date DATE, \n\treceive_date DATE, \n\tdemand_source VARCHAR(200), \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(from_warehouse_id) REFERENCES warehouses (id), \n\tFOREIGN KEY(to_warehouse_id) REFERENCES warehouses (id)\n);'))
        op.execute(sa.text('CREATE TABLE batches (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tpurchase_order_id INTEGER, \n\tsupplier_id INTEGER, \n\tactual_unit_cost NUMERIC(12, 2) NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tin_date DATE NOT NULL, \n\texpiry_date DATE, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id), \n\tFOREIGN KEY(supplier_id) REFERENCES suppliers (id)\n);'))
        op.execute(sa.text('CREATE TABLE purchase_order_lines (\n\tid SERIAL NOT NULL, \n\tpo_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tunit_price NUMERIC(12, 2) NOT NULL, \n\ttotal_price NUMERIC(14, 2) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(po_id) REFERENCES purchase_orders (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id)\n);'))
        op.execute(sa.text('CREATE TABLE sales_order_lines (\n\tid SERIAL NOT NULL, \n\tso_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tunit_price NUMERIC(12, 2) NOT NULL, \n\tdiscount_amount NUMERIC(14, 2) NOT NULL, \n\tnet_amount NUMERIC(14, 2) NOT NULL, \n\tcost_amount NUMERIC(14, 2) NOT NULL, \n\tcost_snapshot TEXT, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(so_id) REFERENCES sales_orders (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id)\n);'))
        op.execute(sa.text('CREATE TABLE stocktakes (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tscope_type VARCHAR(20) NOT NULL, \n\twarehouse_id INTEGER, \n\tlocation_id INTEGER, \n\titem_id INTEGER, \n\tstatus VARCHAR(20) NOT NULL, \n\tstarted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tfinished_at TIMESTAMP WITHOUT TIME ZONE, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(warehouse_id) REFERENCES warehouses (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id)\n);'))
        op.execute(sa.text('CREATE TABLE allocations (\n\tid SERIAL NOT NULL, \n\tdoc_type VARCHAR(20) NOT NULL, \n\tdoc_id INTEGER NOT NULL, \n\tdoc_line_id INTEGER, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tlocation_id INTEGER NOT NULL, \n\tqty NUMERIC(14, 3) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE TABLE audit_logs (\n\tid SERIAL NOT NULL, \n\toperator_id INTEGER, \n\toperator_name VARCHAR(100), \n\taction VARCHAR(50) NOT NULL, \n\tdoc_type VARCHAR(30), \n\tdoc_id VARCHAR(50), \n\titem_id INTEGER, \n\tbatch_id INTEGER, \n\tlocation_id INTEGER, \n\tqty NUMERIC(14, 3), \n\treason VARCHAR(200), \n\tdetail TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(operator_id) REFERENCES users (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE INDEX ix_audit_created_at ON audit_logs (created_at);'))
        op.execute(sa.text('CREATE TABLE cost_consumptions (\n\tid SERIAL NOT NULL, \n\tdoc_type VARCHAR(20) NOT NULL, \n\tdoc_id INTEGER NOT NULL, \n\tdoc_line_id INTEGER, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tqty NUMERIC(14, 3) NOT NULL, \n\tunit_cost NUMERIC(12, 2) NOT NULL, \n\tamount NUMERIC(14, 2) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id)\n);'))
        op.execute(sa.text('CREATE TABLE grn_lines (\n\tid SERIAL NOT NULL, \n\tgrn_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tlocation_id INTEGER NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tactual_unit_cost NUMERIC(12, 2) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(grn_id) REFERENCES grn (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE TABLE returns (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(30) NOT NULL, \n\tsource_type VARCHAR(20) NOT NULL, \n\tsource_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\treason VARCHAR(100) NOT NULL, \n\toperator_id INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(operator_id) REFERENCES users (id)\n);'))
        op.execute(sa.text('CREATE TABLE shipping_order_lines (\n\tid SERIAL NOT NULL, \n\tsh_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tlocation_id INTEGER NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(sh_id) REFERENCES shipping_orders (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE TABLE stock_adjustment_lines (\n\tid SERIAL NOT NULL, \n\tadj_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER, \n\tlocation_id INTEGER NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tnote TEXT, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(adj_id) REFERENCES stock_adjustments (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE TABLE stock_balances (\n\tid SERIAL NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tlocation_id INTEGER NOT NULL, \n\tqty NUMERIC(14, 3) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_balance_item_batch_location UNIQUE (item_id, batch_id, location_id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE TABLE stock_ledger (\n\tid SERIAL NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tlocation_id INTEGER NOT NULL, \n\tqty NUMERIC(14, 3) NOT NULL, \n\tmove_type VARCHAR(20) NOT NULL, \n\tsource_type VARCHAR(30), \n\tsource_id INTEGER, \n\toperator_id INTEGER, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id), \n\tFOREIGN KEY(operator_id) REFERENCES users (id)\n);'))
        op.execute(sa.text('CREATE INDEX ix_ledger_batch ON stock_ledger (batch_id);'))
        op.execute(sa.text('CREATE INDEX ix_ledger_item_location ON stock_ledger (item_id, location_id);'))
        op.execute(sa.text('CREATE TABLE stocktake_lines (\n\tid SERIAL NOT NULL, \n\tstocktake_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tlocation_id INTEGER NOT NULL, \n\tbook_qty NUMERIC(14, 3) NOT NULL, \n\tcounted_qty NUMERIC(14, 3), \n\tdiff_qty NUMERIC(14, 3), \n\treason VARCHAR(100), \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(stocktake_id) REFERENCES stocktakes (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(location_id) REFERENCES locations (id)\n);'))
        op.execute(sa.text('CREATE TABLE transfer_order_lines (\n\tid SERIAL NOT NULL, \n\tto_id INTEGER NOT NULL, \n\titem_id INTEGER NOT NULL, \n\tbatch_id INTEGER NOT NULL, \n\tfrom_location_id INTEGER NOT NULL, \n\tquantity NUMERIC(14, 3) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(to_id) REFERENCES transfer_orders (id), \n\tFOREIGN KEY(item_id) REFERENCES items (id), \n\tFOREIGN KEY(batch_id) REFERENCES batches (id), \n\tFOREIGN KEY(from_location_id) REFERENCES locations (id)\n);'))


def downgrade():
        op.execute(sa.text('DROP TABLE IF EXISTS transfer_order_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS stocktake_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS stock_ledger;'))
        op.execute(sa.text('DROP TABLE IF EXISTS stock_balances;'))
        op.execute(sa.text('DROP TABLE IF EXISTS stock_adjustment_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS shipping_order_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS returns;'))
        op.execute(sa.text('DROP TABLE IF EXISTS grn_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS cost_consumptions;'))
        op.execute(sa.text('DROP TABLE IF EXISTS audit_logs;'))
        op.execute(sa.text('DROP TABLE IF EXISTS allocations;'))
        op.execute(sa.text('DROP TABLE IF EXISTS stocktakes;'))
        op.execute(sa.text('DROP TABLE IF EXISTS sales_order_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS purchase_order_lines;'))
        op.execute(sa.text('DROP TABLE IF EXISTS batches;'))
        op.execute(sa.text('DROP TABLE IF EXISTS transfer_orders;'))
        op.execute(sa.text('DROP TABLE IF EXISTS stock_adjustments;'))
        op.execute(sa.text('DROP TABLE IF EXISTS shipping_orders;'))
        op.execute(sa.text('DROP TABLE IF EXISTS sales_orders;'))
        op.execute(sa.text('DROP TABLE IF EXISTS reorder_points;'))
        op.execute(sa.text('DROP TABLE IF EXISTS purchase_orders;'))
        op.execute(sa.text('DROP TABLE IF EXISTS locations;'))
        op.execute(sa.text('DROP TABLE IF EXISTS item_suppliers;'))
        op.execute(sa.text('DROP TABLE IF EXISTS grn;'))
        op.execute(sa.text('DROP TABLE IF EXISTS warehouses;'))
        op.execute(sa.text('DROP TABLE IF EXISTS users;'))
        op.execute(sa.text('DROP TABLE IF EXISTS suppliers;'))
        op.execute(sa.text('DROP TABLE IF EXISTS items;'))
        op.execute(sa.text('DROP TABLE IF EXISTS customers;'))

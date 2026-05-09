-- =====================================================================
-- 演示用：业务库 (biz) + 语义层 (rag) 种子数据
--
-- 目标租户：meta.tenants.code = 'e2e'（与你的联调账号一致）
--
-- 用法（宿主机）：
--   podman exec -i aichatbot-postgres psql -U postgres -d aichatbot -v ON_ERROR_STOP=1 < scripts/seed_demo_data.sql
--
-- 可重复执行：语义表用 ON CONFLICT UPSERT；demo_orders 按 order_no 先删后插
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS biz.demo_orders (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES meta.tenants (id) ON DELETE CASCADE,
    order_no TEXT NOT NULL,
    product_name TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    region TEXT NOT NULL,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_demo_orders_tenant_order_no
    ON biz.demo_orders (tenant_id, order_no);

GRANT SELECT ON TABLE biz.demo_orders TO biz_ro;

INSERT INTO biz.sample_ping (note)
SELECT v
FROM unnest(
         ARRAY[
             '联调-样例行A',
             '联调-样例行B',
             '联调-销售额备注',
             '演示-华东订单备注'
         ]
     ) AS t (v)
WHERE NOT EXISTS (
        SELECT 1 FROM biz.sample_ping WHERE note = v
    );

DELETE FROM biz.demo_orders o
    USING meta.tenants t
WHERE o.tenant_id = t.id
  AND t.code = 'e2e'
  AND o.order_no LIKE 'DEMO-%';

INSERT INTO biz.demo_orders (tenant_id, order_no, product_name, amount, region, order_date)
SELECT tid,
       x.order_no,
       x.product_name,
       x.amount::numeric,
       x.region,
       x.order_date::date
FROM (SELECT id AS tid FROM meta.tenants WHERE code = 'e2e' LIMIT 1) AS tenant
CROSS JOIN (
             VALUES
                 ('DEMO-001', '蓝牙耳机', 299.00, '华东', '2026-01-15'),
                 ('DEMO-002', '移动电源', 159.50, '华东', '2026-01-18'),
                 ('DEMO-003', '机械键盘', 459.00, '华北', '2026-02-01'),
                 ('DEMO-004', '蓝牙耳机', 279.00, '华南', '2026-02-05'),
                 ('DEMO-005', '显示器支架', 129.00, '华东', '2026-03-10')
         ) AS x(order_no, product_name, amount, region, order_date);


DO $$
DECLARE
    tid   UUID;
    ping_id UUID;
    demo_id UUID;
BEGIN
    SELECT id INTO tid FROM meta.tenants WHERE code = 'e2e' LIMIT 1;
    IF tid IS NULL THEN
        RAISE EXCEPTION '未找到租户 code=e2e，请先创建租户与用户后再执行本脚本';
    END IF;

    INSERT INTO rag.semantic_tables (
        tenant_id,
        schema_name,
        table_name,
        display_name,
        description
    )
    VALUES (
        tid,
        'biz',
        'sample_ping',
        '样例Ping表',
        '小型联调样例：主键 id、备注 note、创建时间 created_at。可用于统计行数等简单问题。'
           )
    ON CONFLICT ON CONSTRAINT uq_semantic_tables_tenant_full_name
        DO UPDATE SET display_name  = EXCLUDED.display_name,
                      description   = EXCLUDED.description,
                      updated_at    = now()
    RETURNING id INTO ping_id;

    IF ping_id IS NULL THEN
        SELECT id INTO ping_id
        FROM rag.semantic_tables
        WHERE tenant_id = tid
          AND schema_name = 'biz'
          AND table_name = 'sample_ping';
    END IF;

    INSERT INTO rag.semantic_columns (
        tenant_id,
        table_id,
        column_name,
        data_type,
        display_name,
        business_meaning
    )
    VALUES
        (
            tid,
            ping_id,
            'id',
            'bigint',
            '主键',
            '自增生成的行标识'
        ),
        (
            tid,
            ping_id,
            'note',
            'text',
            '备注文本',
            '该行样例的说明内容'
        ),
        (
            tid,
            ping_id,
            'created_at',
            'timestamptz',
            '入库时间',
            '记录插入时间'
        )
    ON CONFLICT ON CONSTRAINT uq_semantic_columns_table_col
        DO UPDATE SET data_type         = EXCLUDED.data_type,
                      display_name      = EXCLUDED.display_name,
                      business_meaning  = EXCLUDED.business_meaning,
                      updated_at        = now();

    INSERT INTO rag.semantic_tables (
        tenant_id,
        schema_name,
        table_name,
        display_name,
        description
    )
    VALUES (
        tid,
        'biz',
        'demo_orders',
        '演示订单明细',
        '多租户演示订单表：按 tenant_id 隔离；含订单号、产品名、金额、大区、下单日期；适合问销售额、按大区汇总等。'
           )
    ON CONFLICT ON CONSTRAINT uq_semantic_tables_tenant_full_name
        DO UPDATE SET display_name  = EXCLUDED.display_name,
                      description   = EXCLUDED.description,
                      updated_at    = now()
    RETURNING id INTO demo_id;

    IF demo_id IS NULL THEN
        SELECT id INTO demo_id
        FROM rag.semantic_tables
        WHERE tenant_id = tid
          AND schema_name = 'biz'
          AND table_name = 'demo_orders';
    END IF;

    INSERT INTO rag.semantic_columns (
        tenant_id,
        table_id,
        column_name,
        data_type,
        display_name,
        business_meaning
    )
    VALUES
        (tid, demo_id, 'id', 'bigint', '主键', '订单行主键'),
        (
            tid,
            demo_id,
            'tenant_id',
            'uuid',
            '租户标识',
            '多租户隔离字段；查询时必须带本租户 id'
        ),
        (tid, demo_id, 'order_no', 'text', '订单号', '业务订单编号'),
        (tid, demo_id, 'product_name', 'text', '产品名称', 'SKU 或商品名'),
        (tid, demo_id, 'amount', 'numeric', '成交金额', '含税或标价金额（演示用）'),
        (tid, demo_id, 'region', 'text', '销售大区', '如华东、华北、华南'),
        (
            tid,
            demo_id,
            'order_date',
            'date',
            '下单日期',
            '订单业务日期'
        )
    ON CONFLICT ON CONSTRAINT uq_semantic_columns_table_col
        DO UPDATE SET data_type         = EXCLUDED.data_type,
                      display_name      = EXCLUDED.display_name,
                      business_meaning  = EXCLUDED.business_meaning,
                      updated_at        = now();

    INSERT INTO rag.semantic_terms (
        tenant_id,
        term,
        definition
    )
    VALUES (
        tid,
        '华东大区',
        '业务上指 region 字段取值为「华东」的订单或客户；在 demo_orders 中用 region 过滤。'
           )
    ON CONFLICT ON CONSTRAINT uq_semantic_terms_tenant_term
        DO UPDATE SET definition = EXCLUDED.definition,
                      updated_at = now();
END $$;

COMMIT;

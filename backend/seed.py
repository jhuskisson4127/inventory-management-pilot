from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.models import Product

Base.metadata.create_all(engine)
rows=[
('SKU-1001','Wireless Mouse','Northstar Supply',34,10,24),('SKU-1002','USB-C Cable','CableWorks',8,15,50),('SKU-1003','Laptop Stand','ErgoSource',12,5,20),('SKU-1004','HDMI Adapter','CableWorks',4,8,30),('SKU-1005','Notebook A5','Paper & Co',120,25,100),
('SKU-1006','Ballpoint Pens (10pk)','Paper & Co',18,20,60),('SKU-1007','Desk Organizer','OfficeHub',7,5,12),('SKU-1008','AA Batteries (4pk)','BrightCell',9,12,36),('SKU-1009','Label Roll','PackRight',42,10,30),('SKU-1010','Shipping Box Small','PackRight',55,20,100),
('SKU-1011','Shipping Box Medium','PackRight',14,20,80),('SKU-1012','Thermal Labels','PrintPro',6,10,40),('SKU-1013','Packing Tape','PackRight',26,12,48),('SKU-1014','Barcode Scanner','Northstar Supply',3,2,5),('SKU-1015','Keyboard','Northstar Supply',16,8,20),
('SKU-1016','Monitor 24 inch','Viewline',5,4,6),('SKU-1017','Webcam HD','Viewline',2,5,10),('SKU-1018','Headset USB','SoundCrew',11,6,15),('SKU-1019','Ethernet Adapter','CableWorks',0,4,20),('SKU-1020','Surge Protector','BrightCell',13,7,18)]
with SessionLocal() as db:
    for sku,name,supplier,quantity,reorder_point,reorder_quantity in rows:
        if not db.scalar(select(Product).where(Product.sku==sku)):
            db.add(Product(sku=sku,name=name,supplier=supplier,quantity=quantity,reorder_point=reorder_point,reorder_quantity=reorder_quantity))
    db.commit()
print(f"Seeded {len(rows)} sample products (existing SKUs preserved).")

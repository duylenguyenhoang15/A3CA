
# 1 If not install
wsl --install 
# 2 Enter wsl env
wsl
# 3 cd to a3ca
cd ....../A3CA/a3ca
# 4 
```
pip install -r requirements.txt 
source venv/bin/activate
python main_cli.py --xsd data/xsd/AUTOSAR_00048.xsd data/arxml_invalid_semantic/Nightmare_Config.arxml
python main_cli.py --xsd data/xsd/AUTOSAR_00048.xsd data/arxml_inputs/*.arxml
```
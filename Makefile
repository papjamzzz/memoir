setup:
	pip3 install -r requirements.txt

run:
	python3 app.py

push:
	git add -A && git commit -m "$(m)" && git push

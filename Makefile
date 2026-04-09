setup:
	pip install -r requirements.txt

run:
	python app.py

push:
	git add -A && git commit -m "$(m)" && git push

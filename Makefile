build:
	docker-compose build

up:
	docker-compose up -d loadbalancer

down:
	docker-compose down
	docker rm -f $(docker ps -aq --filter network=net1) 2>/dev/null || true

logs:
	docker logs -f loadbalancer

clean: down
	docker network rm net1 2>/dev/null || true
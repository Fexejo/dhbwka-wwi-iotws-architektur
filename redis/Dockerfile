FROM redis:6.2

COPY redis.conf /etc/redis.conf
RUN echo vm.overcommit_memory = 1 >> /etc/systctl.conf

VOLUME /data

CMD [ "redis-server", "/etc/redis.conf" ]
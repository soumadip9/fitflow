FROM node:20

WORKDIR /app

COPY . .

WORKDIR /app/frontend

RUN rm -rf node_modules package-lock.json

RUN npm install

RUN npm install @rollup/rollup-linux-x64-gnu --save-optional

RUN npm run build

RUN npm install -g serve

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]

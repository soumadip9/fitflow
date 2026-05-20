FROM node:20

WORKDIR /app

COPY . .

RUN npm install --no-package-lock

RUN npm run build

EXPOSE 5173

CMD ["npm", "run", "dev"]

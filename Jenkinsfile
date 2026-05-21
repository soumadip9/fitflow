pipeline {
    agent any

    environment {

        // Docker Hub Credentials
        DOCKERHUB_CREDENTIALS = credentials('dockerhub-token')

        // Docker Image Name
        DOCKER_IMAGE = "soumadipghosh/fitflow"

        // SonarQube Token
        SONAR_TOKEN = credentials('sonar-token')
    }

    stages {

        stage('Checkout') {
            steps {

                // Pull latest code from GitHub
                checkout scm
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {

                    echo "Running SonarQube Scan..."

                    bat """
                    sonar-scanner ^
                    -Dsonar.projectKey=fitflow ^
                    -Dsonar.sources=. ^
                    -Dsonar.host.url=http://localhost:9000 ^
                    -Dsonar.login=%SONAR_TOKEN%
                    """
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {

                    echo "Building Docker Image..."

                    bat "docker build -t ${DOCKER_IMAGE}:latest ."
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                script {

                    echo "Logging into Docker Hub..."

                    bat """
                    echo %DOCKERHUB_CREDENTIALS_PSW% | docker login -u %DOCKERHUB_CREDENTIALS_USR% --password-stdin
                    """

                    echo "Pushing Image to Docker Hub..."

                    bat """
                    docker push ${DOCKER_IMAGE}:latest
                    exit 0
                    """
                }
            }
        }
    }
}

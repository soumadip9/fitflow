pipeline {
    agent any

    environment {

        DOCKERHUB_CREDENTIALS = credentials('dockerhub-token')

       
        DOCKER_IMAGE = "soumadipghosh/fitflow"

        SONAR_TOKEN = credentials('sonar-token')
    }

    stages {

        stage('Checkout') {
            steps {

             
                checkout scm
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {

                    echo "Running SonarQube Scan..."

                    def scannerHome = tool 'sonar-scanner'

                    bat """
                    ${scannerHome}\\bin\\sonar-scanner.bat ^
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

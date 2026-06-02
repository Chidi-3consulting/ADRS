<?php
require_once __DIR__ . '/Exception.php';
require_once __DIR__ . '/SMTP.php';

class PHPMailer
{
    public $Host;
    public $SMTPAuth = false;
    public $Username;
    public $Password;
    public $SMTPSecure;
    public $Port;
    public $From;
    public $FromName;
    public $Subject;
    public $Body;
    protected $to = [];
    protected $isHtml = false;

    public function __construct($exceptions = false)
    {
        if ($exceptions) {
            // no-op
        }
    }

    public function isSMTP()
    {
        $this->SMTPAuth = true;
    }

    public function setFrom(string $address, string $name = ''): void
    {
        $this->From = $address;
        $this->FromName = $name;
    }

    public function addAddress(string $address): void
    {
        $this->to[] = $address;
    }

    public function isHTML(bool $isHtml): void
    {
        $this->isHtml = $isHtml;
    }

    public function send(): bool
    {
        if (empty($this->to)) {
            throw new Exception('No recipients provided');
        }

        $headers = "From: {$this->FromName} <{$this->From}>\r\n";
        if ($this->isHtml) {
            $headers .= "MIME-Version: 1.0\r\n";
            $headers .= "Content-type: text/html; charset=utf-8\r\n";
        }

        return mail($this->to[0], $this->Subject, $this->Body, $headers);
    }
}
